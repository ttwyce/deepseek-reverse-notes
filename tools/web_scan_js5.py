import re
src = open(r"F:\dshh\deepseeka\work\web_main.js", encoding="utf-8", errors="replace").read()
for pat in ['timezoneOffsetSeconds:', 'platform:"web"', 'brand:"', 'x-client-platform']:
    hits = [m.start() for m in re.finditer(re.escape(pat), src)]
    print(f"=== {pat}: {len(hits)}")
    for h in hits[:4]:
        print("   ...", src[max(0,h-300):h+300].replace("\n"," "))
