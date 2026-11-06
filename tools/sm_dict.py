"""提取 deob SDK 中指定对象的字面量定义，按键断行输出。
用法: python tools/sm_dict.py _0x2bdc70 [--out work/sm/dict_x.js]
"""
import sys

s = open(r"work\sm\captcha-sdk.deob.js", encoding="utf-8", errors="replace").read()
name = sys.argv[1]
start = s.find(name + "={")
if start < 0:
    start = s.find(name + " = {")
if start < 0:
    print("not found:", name)
    sys.exit(1)
i = s.index("{", start)
depth = 0
while i < len(s):
    c = s[i]
    if c in "'\"":
        q = c
        i += 1
        while i < len(s):
            if s[i] == "\\":
                i += 2
                continue
            if s[i] == q:
                break
            i += 1
    elif c == "{":
        depth += 1
    elif c == "}":
        depth -= 1
        if depth == 0:
            break
    i += 1
body = s[start : i + 1]

# 按键断行
out = []
depth = 0
j = 0
while j < len(body):
    c = body[j]
    if c in "'\"":
        q = c
        out.append(c)
        j += 1
        while j < len(body):
            out.append(body[j])
            if body[j] == "\\":
                out.append(body[j + 1])
                j += 2
                continue
            if body[j] == q:
                j += 1
                break
            j += 1
        continue
    if c in "([{":
        depth += 1
    elif c in ")]}":
        depth -= 1
    out.append(c)
    if depth == 1 and c == ",":
        out.append("\n")
    j += 1

txt = "".join(out)
if "--out" in sys.argv:
    p = sys.argv[sys.argv.index("--out") + 1]
    open(p, "w", encoding="utf-8").write(txt)
    print("wrote", p, len(txt))
else:
    print(txt)
