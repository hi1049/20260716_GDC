import os
import urllib.request
import urllib.parse
import json
from datetime import datetime

def parse_env(file_path):
    env_vars = {}
    if not os.path.exists(file_path):
        return env_vars
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

def test_request(url, params=None, service_key=None, raw_append=False):
    full_url = url
    if not (full_url.startswith('http://') or full_url.startswith('https://')):
        full_url = 'https://' + full_url

    headers = {
        'User-Agent': 'Mozilla/5.0'
    }

    if raw_append and service_key:
        connector = '&' if '?' in full_url else '?'
        full_url = f"{full_url}{connector}serviceKey={service_key}"
        if params:
            query_string = urllib.parse.urlencode(params)
            full_url = f"{full_url}&{query_string}"
    else:
        query_params = {}
        if service_key:
            query_params['serviceKey'] = service_key
        if params:
            query_params.update(params)
        if query_params:
            connector = '&' if '?' in full_url else '?'
            query_string = urllib.parse.urlencode(query_params)
            full_url = f"{full_url}{connector}{query_string}"

    try:
        req = urllib.request.Request(full_url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            status = response.status
            body = response.read()
            try:
                decoded_body = body.decode('utf-8')
            except UnicodeDecodeError:
                decoded_body = body.decode('euc-kr', errors='replace')
            return True, status, decoded_body
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode('utf-8', errors='replace')
        except Exception:
            err_body = ""
        return False, e.code, f"HTTPError: {e.reason}\nBody: {err_body}"
    except urllib.error.URLError as e:
        return False, None, f"URLError: {e.reason}"
    except Exception as e:
        return False, None, f"Exception: {str(e)}"

def run_tests():
    env = parse_env('.env')
    print("=" * 60)
    print("STARTING COMPREHENSIVE API TEST")
    print("=" * 60)
    
    # Keys
    enc_key = env.get('KPX_TODAY_POWER_STATUS_ENCODING_KEY')
    dec_key = env.get('KPX_TODAY_POWER_STATUS_DECODING_KEY')
    
    today_str = datetime.now().strftime("%Y%m%d")

    # Group 1: 오늘전력수급현황조회
    print("\n[GROUP 1] 한국전력거래소_오늘전력수급현황조회")
    endpoints1 = [
        # KPX Direct
        "https://openapi.kpx.or.kr/openapi/sukub5mToday/getSukub5mToday",
        # apis.data.go.kr (with and without operation name)
        "https://apis.data.go.kr/B552115/Sukub5mToday/getSukub5mToday",
        "https://apis.data.go.kr/B552115/Sukub5mToday",
    ]
    
    for ep in endpoints1:
        print(f"\n--- Testing Endpoint: {ep} ---")
        for key_type, key in [("Encoding (Raw Append)", enc_key), ("Decoding (Urlencoded)", dec_key)]:
            # Test default request
            ok, code, body = test_request(ep, service_key=key, raw_append=("Raw" in key_type))
            print(f"  > Method: {key_type} (Default params)")
            print(f"    Success={ok}, Code={code}, Snippet: {body[:300]}")
            
            # Test with common parameters
            params = {"pageNo": "1", "numOfRows": "10", "_type": "json"}
            ok, code, body = test_request(ep, params=params, service_key=key, raw_append=("Raw" in key_type))
            print(f"  > Method: {key_type} (with pageNo, numOfRows, _type=json)")
            print(f"    Success={ok}, Code={code}, Snippet: {body[:300]}")

    # Group 2: 현재전력수급현황조회
    print("\n[GROUP 2] 한국전력거래소_현재전력수급현황조회")
    endpoints2 = [
        # KPX Direct
        "https://openapi.kpx.or.kr/openapi/sukub5mMaxDatetime/getSukub5mMaxDatetime",
        # apis.data.go.kr variants
        "https://apis.data.go.kr/B552115/sukub/sukubRealtime",
        "https://apis.data.go.kr/B552115/sukub/sukubRealtime/getSukubRealtime",
        "https://apis.data.go.kr/B552115/sukub5mMaxDatetime/getSukub5mMaxDatetime",
    ]
    
    for ep in endpoints2:
        print(f"\n--- Testing Endpoint: {ep} ---")
        for key_type, key in [("Encoding (Raw Append)", enc_key), ("Decoding (Urlencoded)", dec_key)]:
            ok, code, body = test_request(ep, service_key=key, raw_append=("Raw" in key_type))
            print(f"  > Method: {key_type} (Default params)")
            print(f"    Success={ok}, Code={code}, Snippet: {body[:300]}")
            
            params = {"pageNo": "1", "numOfRows": "10", "_type": "json"}
            ok, code, body = test_request(ep, params=params, service_key=key, raw_append=("Raw" in key_type))
            print(f"  > Method: {key_type} (with pageNo, numOfRows, _type=json)")
            print(f"    Success={ok}, Code={code}, Snippet: {body[:300]}")

    # Group 3: 현재전력수급현황조회_GW (sukub5mMaxDatetime2)
    print("\n[GROUP 3] 한국전력거래소_현재전력수급현황조회_GW")
    endpoints3 = [
        "https://apis.data.go.kr/B552115/sukub5mMaxDatetime2/getSukub5mMaxDatetime2",
        "https://apis.data.go.kr/B552115/sukub5mMaxDatetime2"
    ]
    
    for ep in endpoints3:
        print(f"\n--- Testing Endpoint: {ep} ---")
        for key_type, key in [("Encoding (Raw Append)", enc_key), ("Decoding (Urlencoded)", dec_key)]:
            # Param options to isolate missing parameter issue
            param_options = [
                # Option 1: pageNo and numOfRows
                {"pageNo": "1", "numOfRows": "10"},
                # Option 2: pageNo, numOfRows, _type=json
                {"pageNo": "1", "numOfRows": "10", "_type": "json"},
                # Option 3: tradeDay
                {"tradeDay": today_str},
                # Option 4: pageNo, numOfRows, tradeDay
                {"pageNo": "1", "numOfRows": "10", "tradeDay": today_str},
                # Option 5: pageNo, numOfRows, tradeDay, _type=json
                {"pageNo": "1", "numOfRows": "10", "tradeDay": today_str, "_type": "json"}
            ]
            
            for i, p in enumerate(param_options, 1):
                ok, code, body = test_request(ep, params=p, service_key=key, raw_append=("Raw" in key_type))
                print(f"  > Method: {key_type} (Params Option {i}: {p})")
                print(f"    Success={ok}, Code={code}, Snippet: {body[:300]}")

if __name__ == '__main__':
    run_tests()
