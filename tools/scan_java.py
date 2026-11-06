"""在 jadx 输出中按关键字扫描 java 文件（快速，逐文件）。"""
import os, sys, re

sys.stdout.reconfigure(encoding="utf-8")
SRC = r"F:\dshh\deepseeka\work\jadx_out\sources"

pats = sys.argv[1:]
if not pats:
    print("usage: scan_java.py <regex> [regex...]")
    sys.exit(1)
rx = re.compile("|".join(pats))

hits = 0
for dirpath, dirnames, filenames in os.walk(SRC):
    for fn in filenames:
        if not fn.endswith(".java"):
            continue
        p = os.path.join(dirpath, fn)
        try:
            txt = open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        if not rx.search(txt):
            continue
        rel = p[len(SRC) + 1:]
        lines = txt.splitlines()
        print("=" * 78)
        print("FILE " + rel + f"  ({len(lines)} lines)")
        for i, ln in enumerate(lines, 1):
            if rx.search(ln):
                s = ln.strip()
                if len(s) > 300:
                    s = s[:300] + "…"
                print(f"  {i}: {s}")
                hits += 1
                if hits > 3000:
                    print("!! too many hits, stop")
                    sys.exit(0)
