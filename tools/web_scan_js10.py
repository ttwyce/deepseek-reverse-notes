import re
src = open(r"F:\dshh\deepseeka\work\web_main.js", encoding="utf-8", errors="replace").read()
hits = [m.start() for m in re.finditer(r'deviceId:', src)]
print("hits", len(hits))
for h in hits[:12]:
    print("---")
    print(src[max(0,h-300):h+300].replace("\n"," "))
