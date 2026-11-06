import re
src = open(r"F:\dshh\deepseeka\work\web_main.js", encoding="utf-8", errors="replace").read()
hits = [m.start() for m in re.finditer(r'\.RISK_DEVICE_DETECTED', src)]
print("hits", len(hits))
for h in hits:
    print("---")
    print(src[max(0,h-600):h+600].replace("\n"," "))
