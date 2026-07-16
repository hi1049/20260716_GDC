import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from kpx_client import KPXClient
from scheduler_engine import SchedulerEngine, TYPICAL_WEEKDAY_RESERVE_RATES, CARBON_SAVINGS_MULTIPLIER, COST_WEIGHTS

app = FastAPI(
    title="VoltWise API",
    description="한국 전력망 연계 ESG 서버 가동 최적화 추천 API",
    version="1.0.0"
)

# 클라이언트 인스턴스 생성
kpx_client = KPXClient()

# 정적 파일 디렉토리 확인 및 생성
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

# ====================================================================
# REST API Endpoints
# ====================================================================

@app.get("/api/status/live")
async def get_live_status():
    """
    한국전력거래소(KPX) 공공데이터 API로부터 실시간 전력수급현황을 조회하고 등급을 계산합니다.
    """
    res = kpx_client.get_current_power_status()
    if not res.get("success"):
        # 실시간 API 장애 대응용 Fallback 처리 (기본 시뮬레이터 제공)
        print("DEBUG - KPXClient failed:", res.get("error"))
        import datetime
        current_hour = datetime.datetime.now().hour
        base_rate = TYPICAL_WEEKDAY_RESERVE_RATES[current_hour]
        
        # 가상의 실시간 데이터 반환
        return {
            "success": True,
            "is_fallback": True,
            "data": {
                "base_datetime": datetime.datetime.now().strftime("%Y%m%d%H%M%S"),
                "current_load_mw": 82000.0,
                "supply_ability_mw": 101000.0,
                "supply_reserve_mw": 19000.0,
                "supply_reserve_rate": base_rate,
                "operational_reserve_mw": 9500.0,
                "operational_reserve_rate": base_rate * 0.5,
                "forecast_load_mw": 90000.0
            },
            "rating": {
                "code": "GREEN" if base_rate >= 15.0 else ("YELLOW" if base_rate >= 10.0 else "ORANGE"),
                "description": "최적 (전력망 여유, 탄소 배출 최소)" if base_rate >= 15.0 else "양호 (보통 부하)"
            }
        }
    
    # 등급 계산
    data = res["data"]
    reserve_rate = data["supply_reserve_rate"]
    
    if reserve_rate >= 15.0:
        rating_code = "GREEN"
        rating_desc = "최적 (전력망 여유, 탄소 배출 최소)"
    elif reserve_rate >= 10.0:
        rating_code = "YELLOW"
        rating_desc = "양호 (일반 전력 수급 상황)"
    elif reserve_rate >= 5.0:
        rating_code = "ORANGE"
        rating_desc = "주의 (전력 수요 상승, 고탄소 발전기 가동)"
    else:
        rating_code = "RED"
        rating_desc = "비상 (전력 극도 혼잡, 대규모 부하 가동 삼가)"
        
    return {
        "success": True,
        "is_fallback": False,
        "data": data,
        "rating": {
            "code": rating_code,
            "description": rating_desc
        }
    }

@app.get("/api/recommend")
async def get_recommendation(duration_hours: int = Query(4, ge=1, le=24, description="서버 가동 소요 시간 (시간 단위)")):
    """
    서버 학습 예정 시간(duration_hours)을 전달받아 향후 24시간 중 최적 가동 시작 시간대 TOP 3를 반환합니다.
    """
    # 실시간 데이터 확보 시도
    live_res = kpx_client.get_current_power_status()
    live_data = live_res if live_res.get("success") else None
    
    recommendations = SchedulerEngine.recommend_schedule(duration_hours, live_data=live_data)
    
    return {
        "success": True,
        "duration_hours": duration_hours,
        "recommendations": recommendations
    }

@app.get("/api/status/history")
async def get_grid_history():
    """
    대시보드 차트 시각화용 24시간 연속 수급 변동 트렌드 프로필 데이터를 생성합니다.
    현재 실시간 전력 상황의 변동을 반영(캘리브레이션)하여 정합성을 보장합니다.
    """
    import datetime
    current_time = datetime.datetime.now()
    current_hour = current_time.hour
    
    # 실시간 전력 상황 반영
    live_res = kpx_client.get_current_power_status()
    offset = 0.0
    if live_res.get("success"):
        live_rate = live_res["data"]["supply_reserve_rate"]
        offset = live_rate - TYPICAL_WEEKDAY_RESERVE_RATES[current_hour]
        
    history_data = []
    for h in range(24):
        # 현재 시간 기준 24시간 타임라인 구성
        target_hour = (current_hour + h - 12) % 24  # 과거 12시간 ~ 미래 12시간 구도
        reserve_rate = max(1.0, TYPICAL_WEEKDAY_RESERVE_RATES[target_hour] + offset)
        
        # 가상의 부하량 계산 (수급 용량이 대략 102GW라고 가정)
        supply_ability = 103000.0
        current_load = supply_ability * (1.0 - (reserve_rate / 100.0))
        
        history_data.append({
            "hour": f"{target_hour:02d}:00",
            "reserve_rate": round(reserve_rate, 2),
            "current_load_gw": round(current_load / 1000.0, 2),
            "carbon_saving_pct": round(CARBON_SAVINGS_MULTIPLIER[target_hour] * 100.0, 1),
            "cost_weight": COST_WEIGHTS[target_hour]
        })
        
    return {
        "success": True,
        "profile_calibrated": live_res.get("success", False),
        "history": history_data
    }

# ====================================================================
# Frontend Routing (Static Files SPA 서빙)
# ====================================================================

# SPA 진입점 라우트 (index.html 직접 반환)
@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return """
    <html>
        <head><title>VoltWise Loading</title></head>
        <body style="background:#111; color:#fff; font-family:sans-serif; display:flex; justify-content:center; align-items:center; height:100vh; margin:0;">
            <div style="text-align:center;">
                <h2>VoltWise 서버리스 애플리케이션 초기화 완료</h2>
                <p style="color:#888;">정적 파일을 생성하는 중입니다. 잠시만 기다려주세요...</p>
            </div>
        </body>
    </html>
    """

# 정적 파일 디렉토리 연결 (CSS, JS 등을 서빙)
app.mount("/static", StaticFiles(directory=static_dir), name="static")
