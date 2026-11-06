import re, requests
s = requests.Session(); s.trust_env = False
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
r = s.get("https://chat.deepseek.com/", headers={"User-Agent": UA}, timeout=30)
print("status", r.status_code, "len", len(r.text))
open(r"F:\dshh\deepseeka\work\web_index.html","w",encoding="utf-8").write(r.text)
for m in re.findall(r'(?:src|href)="([^"]+\.(?:js|css))"', r.text):
    print("ASSET", m)
