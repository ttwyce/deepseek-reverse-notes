"""在 dex 字符串表中按正则检索（可复用）。用法: python g.py <正则> [上限] [最小长度]"""
import re, sys

sys.stdout.reconfigure(encoding="utf-8")
PATH = r"F:\dshh\deepseeka\work\dex_strings.txt"
pat = re.compile(sys.argv[1], re.I)
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 200
minlen = int(sys.argv[3]) if len(sys.argv) > 3 else 0

hits = []
with open(PATH, encoding="utf-8", errors="ignore") as f:
    for line in f:
        s = line.rstrip("\n")
        if len(s) < minlen:
            continue
        if pat.search(s):
            hits.append(s)
print(f"[{len(hits)} hits] pattern={sys.argv[1]}")
for h in hits[:limit]:
    print(repr(h))
