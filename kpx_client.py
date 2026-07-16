import os
import urllib.request
import urllib.parse
import json
from datetime import datetime

class KPXClient:
    def __init__(self, env_path=".env"):
        self.env = self._parse_env(env_path)
        # 100% 검증된 GW 수급 엔드포인트를 기본 사용합니다.
        self.gw_endpoint = "https://apis.data.go.kr/B552115/sukub5mMaxDatetime2/getSukub5mMaxDatetime2"
        self.gw_key = self.env.get("KPX_CURRENT_POWER_STATUS_GW_ENCODING_KEY")

    def _parse_env(self, file_path):
        env_vars = {}
        if not os.path.exists(file_path):
            # 로컬 환경 변수에서 대체 탐색
            return os.environ
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, val = line.split('=', 1)
                    key = key.strip()
                    val = val.strip().strip("'").strip('"')
                    env_vars[key] = val
        return env_vars

    def get_current_power_status(self):
        """
        한국전력거래소 현재전력수급현황조회 (GW) API를 호출하여 실시간 데이터 반환
        """
        if not self.gw_key:
            raise ValueError("KPX_CURRENT_POWER_STATUS_GW_ENCODING_KEY가 .env 파일에 설정되어 있지 않습니다.")

        params = {
            "dataType": "json"
        }
        
        # 공공데이터포털 특성 상 Encoding Key는 이미 인코딩되어 있으므로 urllib.parse.quote를 피해야 함
        # 따라서 URL 파라미터를 수동 조합하거나 raw_append 구조를 취함
        query_string = urllib.parse.urlencode(params)
        url = f"{self.gw_endpoint}?serviceKey={self.gw_key}&{query_string}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)'
        }
        
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as response:
                if response.status != 200:
                    return {"success": False, "error": f"HTTP Status {response.status}"}
                
                body = response.read().decode('utf-8', errors='replace')
                data = json.loads(body)
                
                # API 응답 결과코드 확인
                res_header = data.get("response", {}).get("header", {})
                result_code = res_header.get("resultCode")
                result_msg = res_header.get("resultMsg")
                
                if result_code != "00":
                    return {"success": False, "error": f"API Error ({result_code}): {result_msg}"}
                
                items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
                if not items:
                    return {"success": False, "error": "응답에 유효한 전력 수급 데이터 아이템이 없습니다."}
                
                # 최신 1개 수급 정보 파싱
                item = items[0]
                
                # 원본 값 추출 및 단위 보정 (MW 단위를 소수점 1자리 MW 단위로 정규화)
                curr_pwr = float(item.get("currPwrTot", 0))  # 현재부하
                supp_ability = float(item.get("suppAbility", 0))  # 공급능력
                supp_reserve = float(item.get("suppReservePwr", 0))  # 공급예비력
                supp_reserve_rate = float(item.get("suppReserveRate", 0))  # 공급예비율
                oper_reserve = float(item.get("operReservePwr", 0))  # 운영예비력
                oper_reserve_rate = float(item.get("operReserveRate", 0))  # 운영예비율
                forecast_load = float(item.get("forecastLoad", 0))  # 예측부하
                base_datetime = item.get("baseDatetime", "")  # 기준시간 (YYYYMMDDHHMMSS)
                
                return {
                    "success": True,
                    "data": {
                        "base_datetime": base_datetime,
                        "current_load_mw": round(curr_pwr, 1),
                        "supply_ability_mw": round(supp_ability, 1),
                        "supply_reserve_mw": round(supp_reserve, 1),
                        "supply_reserve_rate": round(supp_reserve_rate, 2),
                        "operational_reserve_mw": round(oper_reserve, 1),
                        "operational_reserve_rate": round(oper_reserve_rate, 2),
                        "forecast_load_mw": round(forecast_load, 1)
                    }
                }
                
        except Exception as e:
            return {"success": False, "error": f"API 호출 중 예외 발생: {str(e)}"}

if __name__ == '__main__':
    # 간단한 테스트 스크립트 실행
    client = KPXClient()
    print("실시간 전력 수급 조회 테스트 중...")
    res = client.get_current_power_status()
    print(json.dumps(res, indent=2, ensure_ascii=False))
