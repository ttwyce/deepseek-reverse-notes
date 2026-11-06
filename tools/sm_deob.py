"""用已导出的 strtab.json 对 captcha-sdk.min.js 做全量字符串还原。
自动收集所有把 _0x3634 赋给局部别名的形式，再替换 alias(0xNNN) 调用。
"""
import json
import re

SRC = r"work\sm\captcha-sdk.min.js"
TAB = r"work\sm\strtab.json"
OUT = r"work\sm\captcha-sdk.deob.js"

raw = open(SRC, encoding="utf-8", errors="replace").read()
s = "".join(c if (c.isprintable() or c == "\n") else " " for c in raw)
tab = json.load(open(TAB, encoding="utf-8"))
print("strtab:", len(tab))

# 1) 收集解码器别名：xxx = _0x3634 （含 var / 逗号 / 参数默认值等）
aliases = {"_0x3634"}
for mo in re.finditer(r"([_$a-zA-Z][\w$]*)\s*=\s*_0x3634\b", s):
    aliases.add(mo.group(1))
# 2) 也收集 alias = 已别名 的链式赋值
changed = True
while changed:
    changed = False
    for mo in re.finditer(r"([_$a-zA-Z][\w$]*)\s*=\s*(" + "|".join(re.escape(a) for a in aliases) + r")\b", s):
        if mo.group(1) not in aliases:
            aliases.add(mo.group(1))
            changed = True
print("aliases:", len(aliases))

cnt = [0]


def repl(mo):
    idx = int(mo.group(1), 16)
    key = str(idx)
    if key in tab:
        cnt[0] += 1
        return json.dumps(tab[key], ensure_ascii=False)
    return mo.group(0)


pat = re.compile(r"\b(" + "|".join(re.escape(a) for a in sorted(aliases, key=len, reverse=True)) + r")\((0x[0-9a-fA-F]+)\)")


def repl2(mo):
    idx = int(mo.group(2), 16)
    if str(idx) in tab:
        cnt[0] += 1
        return json.dumps(tab[str(idx)], ensure_ascii=False)
    return mo.group(0)


s2 = pat.sub(repl2, s)
print("replaced:", cnt[0])
open(OUT, "w", encoding="utf-8").write(s2)
print("out:", OUT, len(s2))
