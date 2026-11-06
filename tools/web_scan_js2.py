import re
src = open(r"F:\dshh\deepseeka\work\web_main.js", encoding="utf-8", errors="replace").read()
for pat in ['/users/login"', 'password:', 'os:"web"', 'os:"', 'deviceSnapshot', 'x-ds-', 'shumei_device_id']:
    hits = [m.start() for m in re.finditer(re.escape(pat), src)]
    print(f"=== {pat}: {len(hits)}")
    for h in hits[:3]:
        print("   ...", src[max(0,h-260):h+260].replace("\n"," "))
