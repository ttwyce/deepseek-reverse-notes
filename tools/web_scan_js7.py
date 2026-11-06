import re
src = open(r"F:\dshh\deepseeka\work\web_main.js", encoding="utf-8", errors="replace").read()
for pat in ['scenario:"', 'scenario:', 'emailVerificationCode', 'LOGIN_ERROR_CODE']:
    hits = [m.start() for m in re.finditer(re.escape(pat), src)]
    print(f"=== {pat}: {len(hits)}")
    seen=set()
    for h in hits[:8]:
        seg = src[max(0,h-120):h+160].replace("\n"," ")
        if seg[:60] in seen: continue
        seen.add(seg[:60])
        print("   ...", seg)
