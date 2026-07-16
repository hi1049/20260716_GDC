import datetime

# 대한민국 표준 산업용 전력 시간대별 요금제 & 탄소 부하 모델 (KPX/KEPCO 기준)
# 1. 경부하 (Light Load): 23:00 ~ 09:00 (가장 저렴, 기저부하 중심, 전력 안정성 최상, 탄소집약도 낮음)
# 2. 중부하 (Medium Load): 09:00 ~ 10:00, 12:00 ~ 13:00, 17:00 ~ 23:00 (보통 부하)
# 3. 최대부하 (Peak Load): 10:00 ~ 12:00, 13:00 ~ 17:00 (가장 비쌈, 첨두부하 발전기 가동, 탄소집약도 높음)

# 시간별 표준 공급 예비율(%) 프로필 (대한민국 사계절 평균 전력 수급 모델 기반)
TYPICAL_WEEKDAY_RESERVE_RATES = [
    26.5, # 00:00 (경부하)
    28.0, # 01:00 (경부하)
    29.5, # 02:00 (경부하)
    30.0, # 03:00 (경부하)
    30.5, # 04:00 (경부하)
    29.0, # 05:00 (경부하)
    27.5, # 06:00 (경부하)
    24.0, # 07:00 (경부하)
    20.5, # 08:00 (경부하)
    16.5, # 09:00 (중부하)
    12.0, # 10:00 (최대부하)
    11.5, # 11:00 (최대부하)
    15.0, # 12:00 (중부하 - 태양광 발전 및 점심시간 일시 하락)
    10.5, # 13:00 (최대부하)
    9.5,  # 14:00 (최대부하 - 일일 최대 피크)
    10.0, # 15:00 (최대부하)
    11.0, # 16:00 (최대부하)
    14.5, # 17:00 (중부하)
    13.0, # 18:00 (중부하)
    13.5, # 19:00 (중부하)
    14.5, # 20:00 (중부하)
    16.0, # 21:00 (중부하)
    19.0, # 22:00 (중부하)
    23.0  # 23:00 (경부하)
]

# 시간별 탄소 절감 계수 (14:00 최대 피크 탄소 배출량 1.0 대비 상대적 친환경 비율)
# 경부하 시간대는 기저부하(원자력 등) 비중이 높아 상대적으로 탄소 배출이 적음
CARBON_SAVINGS_MULTIPLIER = [
    0.35, # 00:00
    0.38, # 01:00
    0.40, # 02:00
    0.40, # 03:00
    0.40, # 04:00
    0.38, # 05:00
    0.35, # 06:00
    0.30, # 07:00
    0.20, # 08:00
    0.10, # 09:00
    0.00, # 10:00 (최대부하 - 탄소 절감률 0%)
    0.00, # 11:00
    0.15, # 12:00
    0.00, # 13:00
    0.00, # 14:00 (최대피크 기준)
    0.00, # 15:00
    0.02, # 16:00
    0.10, # 17:00
    0.08, # 18:00
    0.08, # 19:00
    0.10, # 20:00
    0.15, # 21:00
    0.20, # 22:00
    0.30  # 23:00
]

# 산업용 전력 단가 요금 가중치 (14:00 최대 피크 전력 가격 1.0 대비 가중치)
COST_WEIGHTS = [
    0.45, # 00:00 (경부하 - 최고 저렴)
    0.45, # 01:00
    0.45, # 02:00
    0.45, # 03:00
    0.45, # 04:00
    0.45, # 05:00
    0.45, # 06:00
    0.45, # 07:00
    0.45, # 08:00
    0.75, # 09:00 (중부하)
    1.00, # 10:00 (최대부하)
    1.00, # 11:00
    0.75, # 12:00
    1.00, # 13:00
    1.00, # 14:00
    1.00, # 15:00
    1.00, # 16:00
    0.75, # 17:00
    0.75, # 18:00
    0.75, # 19:00
    0.75, # 20:00
    0.75, # 21:00
    0.75, # 22:00
    0.45  # 23:00
]

def get_status_level(reserve_rate):
    if reserve_rate >= 15.0:
        return "GREEN", "최적 (전력망 여유, 탄소 배출 최소)"
    elif reserve_rate >= 10.0:
        return "YELLOW", "양호 (일반 전력 수급 상황)"
    elif reserve_rate >= 5.0:
        return "ORANGE", "주의 (전력 수요 상승, 고탄소 발전기 가동)"
    else:
        return "RED", "비상 (전력 극도 혼잡, 대규모 부하 가동 삼가)"

class SchedulerEngine:
    @staticmethod
    def recommend_schedule(duration_hours: int, live_data: dict = None):
        """
        사용자의 요구 학습 시간(duration_hours)을 입력받아,
        향후 24시간 내 가장 ESG 점수가 높고 저렴하며 전력망이 안정적인 최적의 가동 시작 시간대를 계산하여 추천합니다.
        
        - live_data: 실시간 전력 데이터가 제공되면, 현재 시간대의 예비율 프로필을 실시간 수치로 동적 보정합니다.
        """
        # 1시간 미만은 최소 1시간으로 처리
        duration_hours = max(1, min(24, duration_hours))
        
        current_time = datetime.datetime.now()
        current_hour = current_time.hour
        
        # 24시간 윈도우 생성 (현재 시간부터 다음날 같은 시간 전까지)
        recommendations = []
        
        # 시간당 프로필 보정 (실시간 데이터를 현재 시간 기준 프로필에 매핑)
        reserve_profiles = list(TYPICAL_WEEKDAY_RESERVE_RATES)
        if live_data and live_data.get("success"):
            live_rate = live_data["data"]["supply_reserve_rate"]
            # 현재 시간대의 표준 프로필을 실시간 관측 데이터로 보정하고 주변 시간대도 자연스럽게 매핑
            offset = live_rate - reserve_profiles[current_hour]
            # 스무딩 계수를 주어 현재 시간대 근처 프로필을 보정
            for i in range(24):
                dist = min(abs(i - current_hour), 24 - abs(i - current_hour))
                # 거리가 가까울수록 실시간 보정치 반영을 크게 함
                influence = max(0, 1 - (dist / 6))
                reserve_profiles[i] += offset * influence
        
        for start_offset in range(24):
            candidate_start_hour = (current_hour + start_offset) % 24
            
            # 총 소요 시간 동안의 평균 값들을 계산
            total_reserve_rate = 0.0
            total_carbon_saving = 0.0
            total_cost_weight = 0.0
            
            for h_offset in range(duration_hours):
                target_hour = (candidate_start_hour + h_offset) % 24
                total_reserve_rate += reserve_profiles[target_hour]
                total_carbon_saving += CARBON_SAVINGS_MULTIPLIER[target_hour]
                total_cost_weight += COST_WEIGHTS[target_hour]
                
            avg_reserve_rate = total_reserve_rate / duration_hours
            avg_carbon_saving_pct = (total_carbon_saving / duration_hours) * 100
            avg_cost_discount_pct = (1.0 - (total_cost_weight / duration_hours)) * 100
            
            # 시간대 라벨링
            target_date = current_time + datetime.timedelta(hours=start_offset)
            if start_offset == 0:
                time_label = f"즉시 가동 ({target_date.strftime('%H:00')})"
            elif target_date.date() == current_time.date():
                time_label = f"오늘 {target_date.strftime('%H:00')}"
            else:
                time_label = f"내일 {target_date.strftime('%H:00')}"
                
            status_code, status_desc = get_status_level(avg_reserve_rate)
            
            recommendations.append({
                "start_offset": start_offset,
                "start_hour": candidate_start_hour,
                "time_label": time_label,
                "avg_reserve_rate": round(avg_reserve_rate, 2),
                "carbon_saving_pct": round(avg_carbon_saving_pct, 1),
                "cost_discount_pct": round(avg_cost_discount_pct, 1),
                "status_code": status_code,
                "status_desc": status_desc,
                # ESG 점수 산출 공식: 전력 예비율과 탄소 절감 계수를 결합한 100점 만점 기준 점수
                "esg_score": round(min(100.0, (avg_reserve_rate * 2.0) + (avg_carbon_saving_pct * 1.2)), 1)
            })
            
        # ESG 점수 및 예비율이 가장 높은 순으로 정렬하여 탑 3 추천 도출
        recommendations.sort(key=lambda x: x["esg_score"], reverse=True)
        
        return recommendations[:3]

if __name__ == '__main__':
    print("스케줄러 엔진 자체 알고리즘 테스트 (예상 학습시간: 4시간)")
    top_3 = SchedulerEngine.recommend_schedule(4)
    for idx, rec in enumerate(top_3, 1):
        print(f"\n[추천 {idx}순위] {rec['time_label']}")
        print(f"  > ESG 종합 점수: {rec['esg_score']} / 100")
        print(f"  > 평균 전력 예비율: {rec['avg_reserve_rate']}%")
        print(f"  > 탄소 배출 감소율: {rec['carbon_saving_pct']}% (최대 피크 시간대 구동 대비)")
        print(f"  > 전력 요금 절감률: {rec['cost_discount_pct']}%")
        print(f"  > 상태 등급: {rec['status_desc']}")
