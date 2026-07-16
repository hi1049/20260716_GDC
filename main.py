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
        raise HTTPException(
            status_code=502,
            detail=f"공공데이터 포털 API 호출 실패: {res.get('error')}"
        )
    
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
        
        # 실시간 데이터 기준 시간별 전력 부하량 계산 (평균 공급능력 103GW 환산 적용)
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

@app.get("/api/status/weekly")
async def get_weekly_status():
    """
    7일 연속 전력망 수급 및 부하량 예측 데이터를 제공합니다.
    주중 전력 과부하 타임 및 주말(토, 일)의 풍부한 예비율 특성을 반영합니다.
    """
    import datetime
    current_time = datetime.datetime.now()
    current_hour = current_time.hour
    
    # 실시간 현재 정보 조회하여 오프셋 보정 적용
    live_res = kpx_client.get_current_power_status()
    offset = 0.0
    if live_res.get("success"):
        live_rate = live_res["data"]["supply_reserve_rate"]
        offset = live_rate - TYPICAL_WEEKDAY_RESERVE_RATES[current_hour]
        
    days_kr = ["월", "화", "수", "목", "금", "토", "일"]
    weekly_data = []
    
    for i in range(7):
        target_date = current_time + datetime.timedelta(days=i)
        weekday_idx = target_date.weekday() # 0=월, 6=일
        
        # 요일별 전력 부하 보정 계수
        # 주말(토/일)은 대규모 산업용 전력 차단으로 부하가 급감하고 예비율이 대폭 상승합니다.
        if weekday_idx == 5: # 토요일
            day_load_multiplier = 0.85
            day_reserve_boost = 7.0
        elif weekday_idx == 6: # 일요일
            day_load_multiplier = 0.75
            day_reserve_boost = 14.0
        else: # 평일
            day_load_multiplier = 1.0
            day_reserve_boost = 0.0
            
        # 요일 일일 수치 산출을 위해 24시간 가중 평균 처리
        daily_reserves = []
        daily_loads = []
        
        for h in range(24):
            # 실시간 오프셋 + 요일별 예비율 보정
            r_rate = max(1.0, TYPICAL_WEEKDAY_RESERVE_RATES[h] + offset + day_reserve_boost)
            daily_reserves.append(r_rate)
            
            # 부하량 계산 (수급 한계 103GW 비례)
            supply_ability = 103000.0
            load_mw = supply_ability * (1.0 - (r_rate / 100.0)) * day_load_multiplier
            daily_loads.append(load_mw)
            
        avg_reserve = sum(daily_reserves) / len(daily_reserves)
        avg_load = sum(daily_loads) / len(daily_loads)
        max_load = max(daily_loads)
        
        # 날짜 레이블 지정 (예: "오늘 (목)", "내일 (금)", "07/18 (토)")
        if i == 0:
            date_label = f"오늘 ({days_kr[weekday_idx]})"
        elif i == 1:
            date_label = f"내일 ({days_kr[weekday_idx]})"
        else:
            date_label = f"{target_date.strftime('%m/%d')} ({days_kr[weekday_idx]})"
            
        # 일별 종합 ESG 점수 산출 (예비율 기준)
        esg_score = min(100.0, max(0.0, (avg_reserve - 10.0) * 4.0 + 50.0))
        if weekday_idx in [5, 6]:
            esg_score = min(100.0, esg_score + 15.0) # 주말 인센티브
            
        weekly_data.append({
            "date": target_date.strftime("%Y-%m-%d"),
            "label": date_label,
            "weekday_idx": weekday_idx,
            "avg_reserve_rate": round(avg_reserve, 2),
            "avg_load_gw": round(avg_load / 1000.0, 2),
            "peak_load_gw": round(max_load / 1000.0, 2),
            "esg_score": round(esg_score, 1),
            "status_code": "GREEN" if avg_reserve >= 18.0 else ("YELLOW" if avg_reserve >= 12.0 else "ORANGE")
        })
        
    return {
        "success": True,
        "weekly": weekly_data
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
