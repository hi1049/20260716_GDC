import urllib.request
import urllib.parse
import os
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

def test():
    env = parse_env('.env')
    service_key = env.get('KPX_TODAY_POWER_STATUS_ENCODING_KEY')
    base_url = "https://apis.data.go.kr/B552115/Sukub5mToday/getSukub5mToday"
    
    headers = {
        'User-Agent': 'Mozilla/5.0'
    }
    
    # Test combinations of dataType and tradeDay
    tests = [
        {"dataType": "json"},
        {"dataType": "json", "tradeDay": datetime.now().strftime("%Y%m%d")},
    ]
    
    for param in tests:
        url = f"{base_url}?serviceKey={service_key}&{urllib.parse.urlencode(param)}"
        print(f"Testing URL: {url}")
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                body = response.read().decode('utf-8', errors='replace')
                print(f"Status: {response.status}")
                print(f"Response: {body[:1000]}\n")
        except Exception as e:
            print(f"Error: {e}\n")

if __name__ == '__main__':
    test()
