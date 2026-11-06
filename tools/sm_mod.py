"""从 deob SDK 中提取指定 webpack 模块，并拼接原始 min.js 的 obfuscator header
（字符串数组函数 + 解码函数 + 旋转 IIFE），使其可独立在 Node 里运行。
用法: python tools/sm_mod.py 0x5b [out]
"""
import sys

MIN = r"work\sm\captcha-sdk.min.js"
DEOB = r"work\sm\captcha-sdk.deob.js"


def match_paren(text, start):
    depth = 0
    i = start
    n = len(text)
    while i < n:
        c = text[i]
        if c in "'\"":
            q = c
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == q:
                    break
                i += 1
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


raw = open(MIN, encoding="utf-8", errors="replace").read()
mins = "".join(c if (c.isprintable() or c == "\n") else " " for c in raw)
# 精简 header：字符串数组函数 + 解码函数 + 旋转 IIFE（不含 webpack bootstrap）
rot_pos = mins.index("}(_0x127b,")
close = mins.index(")", rot_pos)
header = mins[: close + 1]

s = open(DEOB, encoding="utf-8", errors="replace").read()
mid = sys.argv[1]
start = s.find(mid + ":[function")
if start < 0:
    print("not found:", mid)
    sys.exit(1)
fstart = s.index("function", start)
i = s.index("{", fstart)
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
body = s[fstart : i + 1]

out = sys.argv[2] if len(sys.argv) > 2 else r"work\sm\mod_%s.js" % mid
open(out, "w", encoding="utf-8").write(
    # 模块体里的字符串表调用已被 sm_deob 全部替换为明文，仅剩别名声明引用 _0x3634，
    # 因此只需一个占位解码器即可脱离 obfuscator header 独立运行。
    "var _0x3634=function(){return '';};\n"
    "module.exports=(function(){\n"
    "var module={exports:{}},exports=module.exports;\n"
    "var fn=" + body + ";\n"
    "fn(function(){return {};},module,module.exports);\n"
    "return module.exports;})();\n"
)
print("wrote", out, "body", len(body), "header", len(header))
