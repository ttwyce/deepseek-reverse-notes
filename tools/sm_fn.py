"""从 deob SDK 中按函数名提取函数体（括号配对），写入 work/sm/fn_<name>.js"""
import re
import sys

s = open(r"work\sm\captcha-sdk.deob.js", encoding="utf-8", errors="replace").read()

name = sys.argv[1]
pats = [
    f"'{name}']=function",
    f'"{name}"]=function',
    f"'{name}'=function",
    f'"{name}"=function',
    f"{name}=function",
]
idx = -1
for p in pats:
    idx = s.find(p)
    if idx >= 0:
        break
if idx < 0:
    print("not found")
    sys.exit(1)

# 从 function 关键字开始做括号配对
fs = s.index("function", idx)
i = s.index("{", fs)
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

body = s[idx : i + 1]
out = rf"work\sm\fn_{name}.js"
open(out, "w", encoding="utf-8").write(body)
print(f"{name}: {len(body)} chars -> {out}")
