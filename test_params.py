import urllib.request
import urllib.parse
import os

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

def test():
    env = parse_env('.env')
    service_key = env.get('KPX_CURRENT_POWER_STATUS_GW_ENCODING_KEY')
    base_url = "https://apis.data.go.kr/B552115/sukub5mMaxDatetime2/getSukub5mMaxDatetime2"
    
    # List of parameter names to test
    param_names = [
        "tradeYmd", "TradeYmd", "tradeymd", "TRADEYMD", "trade_ymd",
        "ymd", "Ymd", "YMD", "tradeDay", "trade_day", "tradeDate"
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0'
    }
    
    # We will test each parameter name with the value "20260716"
    for name in param_names:
        url = f"{base_url}?serviceKey={service_key}&{name}=20260716"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                body = response.read().decode('utf-8', errors='replace')
                if '"resultCode" : "11"' not in body and '필수요청' not in body:
                    print(f"[FOUND POSSIBLE MATCH] Param: {name}")
                    print(f"URL: {url}")
                    print(f"Response: {body}\n")
                else:
                    print(f"Param '{name}' failed with resultCode 11")
        except Exception as e:
            print(f"Error testing {name}: {e}")

if __name__ == '__main__':
    test()
