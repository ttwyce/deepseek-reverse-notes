import re, sys
sys.stdout.reconfigure(encoding="utf-8")
d = open(sys.argv[1], "rb").read()
ss = re.findall(rb"[ -~]{6,}", d)
seen = []
idx = {}
for s in ss:
    t = s.decode()
    if t in idx:
        continue
    idx[t] = len(seen)
    seen.append(t)
print("total unique:", len(seen))
start = int(sys.argv[2]) if len(sys.argv) > 2 else 0
for t in seen[start:]:
    if "rustc" in t or "gimli" in t or "libunwind" in t or "DW_" in t or "addr2line" in t:
        continue
    print(t)
