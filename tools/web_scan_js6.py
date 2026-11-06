import re
src = open(r"F:\dshh\deepseeka\work\web_main.js", encoding="utf-8", errors="replace").read()
for pat in ['HP:(', 'HP:()=>', 'getBrand:', 'clientPlatform']:
    hits = [m.start() for m in re.finditer(re.escape(pat), src)]
    print(f"=== {pat}: {len(hits)}")
    for h in hits[:3]:
        print("   ...", src[max(0,h-200):h+320].replace("\n"," "))
