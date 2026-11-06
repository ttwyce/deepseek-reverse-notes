"""静态扫描 captcha-sdk.min.js，把关键词上下文以纯 ASCII JSON 落盘（供 read 工具安全读取）。"""
import json
import re

SRC = r"work\sm\captcha-sdk.min.js"
OUT = r"work\sm\sdk_ctx.json"
s = open(SRC, encoding="utf-8", errors="replace").read()
# 清理不可打印字符
s = "".join(ch if (ch.isprintable() or ch == "\n") else " " for ch in s)

TARGETS = ["fverify", "fVerify", "riskLevel", "base64", "captchaUuid", "track", "spatial"]
res = {"size": len(s), "hits": {}}

for t in TARGETS:
    out = []
    for m in re.finditer(re.escape(t), s):
        pos = m.start()
        out.append({"pos": pos, "ctx": s[max(0, pos - 700): pos + 700]})
    res["hits"][t] = out[:6]

# rid 命中太多，只取前 8 且窗口小
out = []
for i, m in enumerate(re.finditer("rid", s)):
    if i >= 8:
        break
    pos = m.start()
    out.append({"pos": pos, "ctx": s[max(0, pos - 300): pos + 300]})
res["hits"]["rid"] = out

# /ca/ 与 fverify 路径常量
res["paths"] = sorted(set(re.findall(r"/(?:ca|pr|crb)/[A-Za-z0-9_./-]{2,60}", s)))

with open(OUT, "w", encoding="ascii") as fh:
    json.dump(res, fh, ensure_ascii=True, indent=1)
print("ok", OUT, res["size"], {k: len(v) for k, v in res["hits"].items()})
