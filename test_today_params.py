import urllib.request
import urllib.parse
import json
import os

def test():
    # Read key
    with open('.env', 'r', encoding='utf-8') as f:
        env = {}
        for line in f:
            if '=' in line and not line.startswith('#'):
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip().strip("'").strip('"')
                
    key = env.get('KPX_TODAY_POWER_STATUS_ENCODING_KEY')
    base_url = "https://apis.data.go.kr/B552115/Sukub5mToday/getSukub5mToday"
    
    headers = {
        'User-Agent': 'Mozilla/5.0'
    }
    
    tests = [
        # Test 1: dataType=json only
        {"dataType": "json"},
        # Test 2: dataType=json, pageNo=1, numOfRows=10
        {"dataType": "json", "pageNo": "1", "numOfRows": "10"},
        # Test 3: _type=json, pageNo=1, numOfRows=10
        {"_type": "json", "pageNo": "1", "numOfRows": "10"},
        # Test 4: baseDate or tradeDay?
    ]
    
    for i, param in enumerate(tests, 1):
        url = f"{base_url}?serviceKey={key}&{urllib.parse.urlencode(param)}"
        print(f"[{i}] Testing URL: {url}")
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as response:
                body = response.read().decode('utf-8', errors='replace')
                print(f"  Status: {response.status}")
                print(f"  Response: {body[:300]}\n")
        except Exception as e:
            print(f"  Error: {e}\n")

if __name__ == '__main__':
    test()
