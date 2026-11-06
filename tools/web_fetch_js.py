import requests
s = requests.Session(); s.trust_env = False
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
for url, name in [("https://fe-static.deepseek.com/chat/static/main.d1d163b7e4.js","main.js"),
                  ("https://fe-static.deepseek.com/chat/static/default-vendors.a2a242fbd2.js","vendors.js")]:
    r = s.get(url, headers={"User-Agent": UA, "Referer":"https://chat.deepseek.com/"}, timeout=120)
    p = r"F:\dshh\deepseeka\work\web_" + name
    open(p,"wb").write(r.content)
    print(name, r.status_code, len(r.content))
