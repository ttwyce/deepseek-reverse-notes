import json, requests, sys
sys.path.insert(0, r"F:\dshh\deepseeka\tools")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
s = requests.Session(); s.trust_env = False
h = {"User-Agent": UA, "Content-Type": "application/json", "Origin": "https://chat.deepseek.com",
     "Referer": "https://chat.deepseek.com/sign_in",
     "x-client-bundle-id": "com.deepseek.chat", "x-client-platform": "web",
     "x-client-version": "2.7.0", "x-client-locale": "zh_CN",
     "x-client-timezone-offset": "28800",
     "x-device-id": "8f3a1c2e-4b5d-4e6f-9a7b-1c2d3e4f5a6b", "x-device-model": ""}
r = s.post("https://chat.deepseek.com/api/v0/users/create_guest_challenge",
           headers=h, data=json.dumps({"target_path": "/api/v0/users/create_email_verification_code"}).encode(), timeout=30)
print(r.status_code)
print(r.text[:600])
