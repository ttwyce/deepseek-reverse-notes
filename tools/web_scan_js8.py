import re
src = open(r"F:\dshh\deepseeka\work\web_main.js", encoding="utf-8", errors="replace").read()
for pat in ['RISK_DEVICE', 'LOGIN_ERROR_CODE||(l.LOGIN_ERROR_CODE={})']:
    hits = [m.start() for m in re.finditer(re.escape(pat), src)]
    print(f"=== {pat}: {len(hits)}")
    for h in hits[:6]:
        print("   ...", src[max(0,h-700):h+700].replace("\n"," "))
        print()
