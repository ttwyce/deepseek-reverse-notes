"""把 fp.min.js 做轻度格式化（仅在字符串外按 ; { } 断行并缩进），便于阅读定位。"""
import os
import sys

SRC = r"work\fp.min.js"
OUT = r"work\sm\fp.min.pretty.js"


def pretty(text: str) -> str:
    out = []
    depth = 0
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in "'\"":
            q = c
            j = i + 1
            buf = [c]
            while j < n:
                if text[j] == "\\":
                    buf.append(text[j:j + 2])
                    j += 2
                    continue
                buf.append(text[j])
                if text[j] == q:
                    j += 1
                    break
                j += 1
            out.append("".join(buf))
            i = j
            continue
        if c == "{":
            depth += 1
            out.append("{\n" + "  " * depth)
            i += 1
            continue
        if c == "}":
            depth = max(0, depth - 1)
            out.append("\n" + "  " * depth + "}")
            i += 1
            continue
        if c == ";":
            out.append(";\n" + "  " * depth)
            i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


raw = open(SRC, encoding="utf-8", errors="replace").read()
s = "".join(c if (c.isprintable() or c == "\n") else " " for c in raw)
res = pretty(s)
with open(OUT, "w", encoding="utf-8") as fh:
    fh.write(res)
print("[out]", OUT, len(res), "chars,", res.count("\n") + 1, "lines")
