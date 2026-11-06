"""从 jadx 反编译源码中提取所有 http(s):// 字面量与域名，聚合并统计。"""
import os, re, sys, collections

sys.stdout.reconfigure(encoding="utf-8")
SRC = r"F:\dshh\deepseeka\work\jadx_out\sources"
rx = re.compile(r'https?://[A-Za-z0-9._~:/?#\[\]@!$&\'()*+,;=%-]+')

hits = collections.Counter()
where = collections.defaultdict(set)

for dirpath, _, filenames in os.walk(SRC):
    for fn in filenames:
        if not fn.endswith(".java"):
            continue
        p = os.path.join(dirpath, fn)
        try:
            txt = open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        for m in rx.finditer(txt):
            u = m.group(0).rstrip('",);')
            # 过滤明显的 docs 链接噪声可保留
            hits[u] += 1
            where[u].add(fn)

lines = []
for u, c in sorted(hits.items()):
    lines.append(f"{c:4d}  {u}")
    for f in sorted(where[u])[:6]:
        lines.append(f"        <- {f}")

open(r"F:\dshh\deepseeka\work\urls_java.txt", "w", encoding="utf-8").write("\n".join(lines))
print("unique urls:", len(hits), "-> work\\urls_java.txt")

# 只打印 deepseek 相关
print("\n=== deepseek 相关 ===")
for u in sorted(hits):
    if "deepseek" in u:
        print(f"{hits[u]:4d}  {u}")
        print("        <- " + ", ".join(sorted(where[u])[:6]))
