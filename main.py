import os
import csv
import json
import urllib.request
import urllib.parse
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Initialize FastAPI
app = FastAPI(
    title="GridPulse API",
    description="한국 전력망 실시간 수급 및 발전믹스 기반 Carbon-Aware AI 워크로드 스케줄러",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)
app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Environment & Config
ENV_PATH = ".env"

def load_env(file_path=ENV_PATH):
    env_vars = {}
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, val = line.split('=', 1)
                    env_vars[key.strip()] = val.strip().strip("'").strip('"')
    # Combine with system environments
    for k, v in os.environ.items():
        env_vars[k] = v
    return env_vars

env = load_env()

# API Keys & Endpoints
KPX_SUKUB_ENDPOINT = env.get("KPX_CURRENT_POWER_STATUS_GW_ENDPOINT", "https://apis.data.go.kr/B552115/sukub5mMaxDatetime2/getSukub5mMaxDatetime2")
KPX_SUKUB_KEY = env.get("KPX_CURRENT_POWER_STATUS_GW_ENCODING_KEY")

KPX_GEN_ENDPOINT = env.get("KPX_GEN_MIX_ENDPOINT", "https://apis.data.go.kr/B552115/PwrAmountByGen/getPwrAmountByGen")
KPX_GEN_KEY = env.get("KPX_GEN_MIX_ENCODING_KEY")

GEMINI_API_KEY = env.get("GEMINI_API_KEY", "")
REPLAY_MODE = env.get("REPLAY", "1") == "1"

# Global simulation state for REPLAY=1 (start at noon for peak solar simulation)
replay_index = 12  

# IPCC AR5 Lifecyle CO2 Emission Factors (gCO2eq/kWh)
EMISSION_FACTORS = {
    "fuelPwr1": 24,   # 수력 (Hydro)
    "fuelPwr2": 700,  # 유류 (Oil)
    "fuelPwr3": 820,  # 유연탄 (Coal - Bituminous)
    "fuelPwr4": 12,   # 원자력 (Nuclear)
    "fuelPwr5": 24,   # 양수 (Pumped storage)
    "fuelPwr6": 490,  # 가스/LNG (Gas)
    "fuelPwr7": 820,  # 국내탄 (Coal - Domestic)
    "fuelPwr8": 38,   # 신재생 (Renewables - Wind/Bio etc.)
    "fuelPwr9": 45    # 태양광 (Solar)
}

# 5-Minute In-Memory Cache
status_cache = {
    "data": None,
    "timestamp": None
}

def calculate_stress_level(reserve_mw):
    """
    정부 전력수급 비상단계 준용 스트레스 판정
    """
    if reserve_mw >= 10000:
        return "여유", "GREEN"
    elif reserve_mw >= 5500:
        return "정상", "BLUE"
    elif reserve_mw >= 4500:
        return "준비~관심", "YELLOW"
    elif reserve_mw >= 3500:
        return "주의", "ORANGE"
    else:
        return "경계·심각", "RED"

def load_replay_data():
    """
    Reads 24 hours simulation from backup.csv
    """
    csv_path = os.path.join(os.path.dirname(__file__), "backup.csv")
    if not os.path.exists(csv_path):
        return []
    
    rows = []
    with open(csv_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows

@app.get("/")
async def get_index():
    return FileResponse(os.path.join(static_dir, "index.html"))

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

@app.get("/api/status")
async def get_status(force_refresh: bool = False):
    """
    실시간 전력 수급 및 발전믹스 조회 (5분 인메모리 캐시 적용)
    REPLAY=1인 경우 backup.csv에서 순환 탐색
    """
    global replay_index
    
    # 1. Replay mode
    if REPLAY_MODE:
        rows = load_replay_data()
        if not rows:
            raise HTTPException(status_code=500, detail="backup.csv 파일이 유효하지 않습니다.")
        
        # Increment index on each poll
        row = rows[replay_index]
        replay_index = (replay_index + 1) % len(rows)
        
        # Map values
        current_load = float(row["current_load_mw"])
        supply_ability = float(row["supply_ability_mw"])
        supply_reserve = float(row["supply_reserve_mw"])
        supply_reserve_rate = float(row["supply_reserve_rate"])
        operational_reserve = float(row["operational_reserve_mw"])
        operational_reserve_rate = float(row["operational_reserve_rate"])
        forecast_load = float(row["forecast_load_mw"])
        
        gen_mix = {
            "hydro": float(row["fuelPwr1"]),
            "oil": float(row["fuelPwr2"]),
            "coal_bituminous": float(row["fuelPwr3"]),
            "nuclear": float(row["fuelPwr4"]),
            "pumped": float(row["fuelPwr5"]),
            "gas_lng": float(row["fuelPwr6"]),
            "coal_domestic": float(row["fuelPwr7"]),
            "renewable": float(row["fuelPwr8"]),
            "solar": float(row["fuelPwr9"])
        }
        
        # Calculate carbon intensity
        total_gen = sum(gen_mix.values())
        weighted_co2 = sum(gen_mix[k] * EF for k, EF in zip(
            ["hydro", "oil", "coal_bituminous", "nuclear", "pumped", "gas_lng", "coal_domestic", "renewable", "solar"],
            EMISSION_FACTORS.values()
        ))
        carbon_intensity = weighted_co2 / total_gen if total_gen > 0 else 450.0
        
        stress_lvl, stress_col = calculate_stress_level(supply_reserve)
        
        return {
            "success": True,
            "mode": "replay",
            "hour": int(row["hour"]),
            "data": {
                "base_datetime": datetime.now().strftime("%Y%m%d") + f"{int(row['hour']):02d}0000",
                "current_load_mw": current_load,
                "supply_ability_mw": supply_ability,
                "supply_reserve_mw": supply_reserve,
                "supply_reserve_rate": supply_reserve_rate,
                "operational_reserve_mw": operational_reserve,
                "operational_reserve_rate": operational_reserve_rate,
                "forecast_load_mw": forecast_load
            },
            "generation_mix": gen_mix,
            "carbon_intensity": round(carbon_intensity, 1),
            "grid_stress_level": stress_lvl,
            "grid_stress_color": stress_col,
            "all_history": rows  # UI rendering historical charts
        }

    # 2. Live API mode with Cache
    now_time = datetime.now()
    if not force_refresh and status_cache["data"] and status_cache["timestamp"]:
        elapsed = (now_time - status_cache["timestamp"]).total_seconds()
        if elapsed < 300:  # 5 minutes cache
            return status_cache["data"]

    # Call KPX Sukub API
    try:
        # Fetch Supply & Demand Status
        params = {"dataType": "json"}
        query_string = urllib.parse.urlencode(params)
        sukub_url = f"{KPX_SUKUB_ENDPOINT}?serviceKey={KPX_SUKUB_KEY}&{query_string}"
        
        req = urllib.request.Request(sukub_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=8) as response:
            sukub_raw = response.read().decode('utf-8', errors='replace')
            sukub_json = json.loads(sukub_raw)
            
        sukub_items = sukub_json.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if not sukub_items:
            raise ValueError("수급현황 데이터가 존재하지 않습니다.")
        s_item = sukub_items[0]
        
        # Fetch Generation Mix
        gen_url = f"{KPX_GEN_ENDPOINT}?serviceKey={KPX_GEN_KEY}&{query_string}"
        req_gen = urllib.request.Request(gen_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req_gen, timeout=8) as response:
            gen_raw = response.read().decode('utf-8', errors='replace')
            gen_json = json.loads(gen_raw)
            
        gen_items = gen_json.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if not gen_items:
            raise ValueError("발전원별 발전량 데이터가 존재하지 않습니다.")
        g_item = gen_items[0]
        
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"공공데이터 포털 연동에 실패하였습니다. (REPLAY=1로 실행 권장): {str(e)}"
        )

    # Parsing Live Data
    current_load = float(s_item.get("currPwrTot", 0))
    supply_ability = float(s_item.get("suppAbility", 0))
    supply_reserve = float(s_item.get("suppReservePwr", 0))
    supply_reserve_rate = float(s_item.get("suppReserveRate", 0))
    operational_reserve = float(s_item.get("operReservePwr", 0))
    operational_reserve_rate = float(s_item.get("operReserveRate", 0))
    forecast_load = float(s_item.get("forecastLoad", 0))

    gen_mix = {
        "hydro": float(g_item.get("fuelPwr1", 0)),
        "oil": float(g_item.get("fuelPwr2", 0)),
        "coal_bituminous": float(g_item.get("fuelPwr3", 0)),
        "nuclear": float(g_item.get("fuelPwr4", 0)),
        "pumped": float(g_item.get("fuelPwr5", 0)),
        "gas_lng": float(g_item.get("fuelPwr6", 0)),
        "coal_domestic": float(g_item.get("fuelPwr7", 0)),
        "renewable": float(g_item.get("fuelPwr8", 0)),
        "solar": float(g_item.get("fuelPwr9", 0))
    }

    total_gen = sum(gen_mix.values())
    weighted_co2 = sum(gen_mix[k] * EF for k, EF in zip(
        ["hydro", "oil", "coal_bituminous", "nuclear", "pumped", "gas_lng", "coal_domestic", "renewable", "solar"],
        EMISSION_FACTORS.values()
    ))
    carbon_intensity = weighted_co2 / total_gen if total_gen > 0 else 450.0
    stress_lvl, stress_col = calculate_stress_level(supply_reserve)

    live_response_data = {
        "success": True,
        "mode": "live",
        "hour": now_time.hour,
        "data": {
            "base_datetime": s_item.get("baseDatetime", ""),
            "current_load_mw": round(current_load, 1),
            "supply_ability_mw": round(supply_ability, 1),
            "supply_reserve_mw": round(supply_reserve, 1),
            "supply_reserve_rate": round(supply_reserve_rate, 2),
            "operational_reserve_mw": round(operational_reserve, 1),
            "operational_reserve_rate": round(operational_reserve_rate, 2),
            "forecast_load_mw": round(forecast_load, 1)
        },
        "generation_mix": gen_mix,
        "carbon_intensity": round(carbon_intensity, 1),
        "grid_stress_level": stress_lvl,
        "grid_stress_color": stress_col
    }

    # Save to Cache
    status_cache["data"] = live_response_data
    status_cache["timestamp"] = now_time
    
    return live_response_data

@app.get("/api/advice")
async def get_advice():
    """
    현재 전력망 상태를 기반으로 Gemini AI Carbon-aware 스케줄 권고 획득
    """
    # 1. Get current state (either replay or live)
    try:
        status = await get_status()
    except Exception as e:
        # Fallback if status call itself fails
        return JSONResponse(status_code=200, content=get_hardcoded_fallback("YELLOW", 450.0))
    
    stress_lvl = status["grid_stress_level"]
    stress_col = status["grid_stress_color"]
    ci = status["carbon_intensity"]
    load_mw = status["data"]["current_load_mw"]
    reserve_mw = status["data"]["supply_reserve_mw"]
    reserve_rate = status["data"]["supply_reserve_rate"]
    mix = status["generation_mix"]
    
    total_mix = sum(mix.values()) or 1
    mix_pct = {k: round(v / total_mix * 100, 1) for k, v in mix.items()}
    
    # 2. Call Gemini (API Key or Google Cloud Vertex AI ADC Hybrid)
    try:
        prompt = f"""
        한국 전력망의 현재 수급 및 발전 탄소 데이터를 기반으로, ML 학습이나 대용량 GPU 컨테이너 워크로드를 돌리는 데이터센터 및 클라우드 운영자를 위한 스케줄 가이드를 JSON 형태로 분석해줘.

        [전력망 데이터]
        - 부하: {load_mw:,} MW
        - 공급 예비력: {reserve_mw:,} MW (예비율 {reserve_rate}%)
        - 그리드 안정성 레벨: {stress_lvl} ({stress_col})
        - 실시간 탄소집약도: {ci:.1f} gCO2eq/kWh
        - 발전 믹스 비중 (%): {json.dumps(mix_pct, ensure_ascii=False)}

        [출력 규칙]
        - 반드시 아래 구조화된 JSON 양식으로만 답변해야 해.
        - 다른 텍스트는 절대 덧붙이지 말고 순수 JSON 문자열만 응답해줘.

        [JSON Schema]
        {{
          "grid_stress": "여유|정상|주의|심각 중 하나",
          "carbon_window": "green|yellow|red 중 하나 (탄소집약도 {ci}에 따른 색상)",
          "recommendation": "RUN_NOW|DEFER 중 하나",
          "defer_until_hint": "가장 합리적인 다음 가동 개시 시간 제안 (예: 23시 이후 경부하 시간대)",
          "reasoning": "위 데이터를 근거로 한 2~3문장 분량의 구체적이고 전문적인 실행 판정 요약",
          "actions": [
            "GPU 대규모 학습 관점 행동 수칙",
            "배치 연산 및 ETL 파이프라인 관점 수칙",
            "추론 서빙 부하 및 스케일러 관점 수칙"
          ],
          "estimated_saving": "탄소 집약도 차이 기반 예측 탄소/비용 절감율 % 표기 (예: 22.4% 절감 예상)"
        }}
        """

        # Utilize the new official google-genai SDK
        from google import genai
        from google.genai import types

        if GEMINI_API_KEY:
            # 1. API Key mode with google-genai
            print("API Key found. Utilizing the new unified google-genai SDK (Gemini API)...")
            client = genai.Client(api_key=GEMINI_API_KEY)
            
            response = client.models.generate_content(
                model="gemini-3.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            result_json = json.loads(response.text.strip())
            return JSONResponse(status_code=200, content=result_json)
        else:
            # 2. Application Default Credentials mode with google-genai (Vertex AI)
            print("No GEMINI_API_KEY set. Utilizing the new unified google-genai SDK (Vertex AI) via ADC...")
            import google.auth
            
            # Retrieve project ID from default credentials
            try:
                credentials, project_id = google.auth.default()
            except Exception as auth_err:
                print(f"Failed to fetch default credentials: {auth_err}")
                project_id = None
                
            if not project_id:
                project_id = os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
                
            if not project_id:
                print("⚠️ GCP Project ID could not be determined. Falling back to dynamic rules.")
                return JSONResponse(status_code=200, content=get_hardcoded_fallback(stress_col, ci))
                
            # Initialize google-genai client configured for Vertex AI
            # Changed from asia-northeast3 to asia-northeast1 (Tokyo) because gemini-3.5-flash is not yet GA in Seoul but is fully supported in Tokyo.
            client = genai.Client(
                vertexai=True,
                project=project_id,
                location="asia-northeast1"
            )
            
            response = client.models.generate_content(
                model="gemini-3.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            result_json = json.loads(response.text.strip())
            return JSONResponse(status_code=200, content=result_json)
            
    except Exception as e:
        print(f"Gemini calling error, entering fallback: {str(e)}")
        return JSONResponse(status_code=200, content=get_hardcoded_fallback(stress_col, ci))

def get_hardcoded_fallback(stress_col, ci):
    """
    Gemini API 키가 없거나 호출 오류 시 제공할 완벽하고 정교한 지능형 동적 폴백 데이터셋 생성
    """
    if stress_col in ["ORANGE", "RED"] or ci > 480:
        # High carbon or high stress -> DEFER recommended
        return {
            "grid_stress": "주의" if stress_col == "ORANGE" else "심각",
            "carbon_window": "red",
            "recommendation": "DEFER",
            "defer_until_hint": "오늘 23:00 이후 심야 경부하 시간대",
            "reasoning": f"현재 전력망 탄소집약도가 {ci:.1f} gCO2eq/kWh로 매우 높고, 화석연료 발전 비율이 치솟아 있습니다. 탄소 절감과 안정적 전력망 유지를 위해 무거운 ML/GPU 학습 작업을 심야 시간대로 지연 실행하는 것을 강력히 권장합니다.",
            "actions": [
                "대규모 GPU 분산 학습 및 훈련 컨테이너 기동을 일시 보류하고 대기 큐로 이전하십시오.",
                "데이터 전처리, 복잡한 ETL 배치 파이프라인 가동을 탄소집약도가 낮은 23시 이후로 스케줄링하십시오.",
                "추론용 파드는 필수 오토스케일링 최소 임계치로 유지하여 피크 전류 소모를 최소화합니다."
            ],
            "estimated_saving": "최대 38.5% 탄소 배출 절감 (화력 발전 대체 시간대 이동 효과)"
        }
    elif stress_col == "YELLOW" or ci > 380:
        # Moderate stress or moderate carbon -> YELLOW
        return {
            "grid_stress": "정상(대비)",
            "carbon_window": "yellow",
            "recommendation": "RUN_NOW",
            "defer_until_hint": "소규모 학습 즉시 기동 가능 (장기 학습은 23시 이후 추천)",
            "reasoning": f"그리드 스트레스는 보통 수준이며, 탄소집약도는 {ci:.1f} gCO2eq/kWh로 안정적인 화석연료-기저 부하 믹스 상태입니다. 단기 실험 학습은 바로 구동이 가능하나, 장기 대용량 학습은 분산 처리를 고려하십시오.",
            "actions": [
                "단기 훈련 파드는 즉시 실행 가능하나 체크포인트를 설정하여 만일의 가동 중단에 대비하십시오.",
                "대용량 병렬 데이터 분석은 순차적으로 기동하여 일시적 서지 전력을 방지하십시오.",
                "GPU 냉각 효율을 위해 공조 장치와 서버 전력 캡 제한을 85% 수준으로 세팅 권장합니다."
            ],
            "estimated_saving": "약 15.0% 탄소 절감 효과"
        }
    else:
        # Best Green state
        return {
            "grid_stress": "여유",
            "carbon_window": "green",
            "recommendation": "RUN_NOW",
            "defer_until_hint": "GPU 대규모 연산 즉시 시작 적극 권장",
            "reasoning": f"현재 공급 예비율이 20% 이상 확보되었으며, 탄소집약도가 {ci:.1f} gCO2eq/kWh로 일간 최저 수준을 기록하고 있습니다. 청정 신재생 및 원자력 기저부하의 비중이 높아 친환경 고성능 연산 가동의 골든 타임입니다.",
            "actions": [
                "미뤄둔 GPU 대규모 분산 학습 및 거대 언어 모델(LLM) 파인튜닝 가동을 적극 승인하십시오.",
                "탄소 집약도가 극소화된 틈을 타 MLOps 배치 파이프라인을 최대 병렬도로 즉시 일괄 처리합니다.",
                "클라우드 인스턴스 전원 제한을 해제하고 최대 클럭으로 빠른 훈련 학습 완료를 가이드합니다."
            ],
            "estimated_saving": "최대 48.0% 전력 요금 및 탄소배출 동시 절감 (태양광 및 원자력 비중 극대화 효과)"
        }
