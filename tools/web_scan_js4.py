import re
src = open(r"F:\dshh\deepseeka\work\web_main.js", encoding="utf-8", errors="replace").read()
for pat in ['x-device', '"x-client', 'deviceModel:', 'K:(e,t,n)', 'K:()=>']:
    hits = [m.start() for m in re.finditer(re.escape(pat), src)]
    print(f"=== {pat}: {len(hits)}")
    for h in hits[:5]:
        print("   ...", src[max(0,h-200):h+240].replace("\n"," "))
