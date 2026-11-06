"""把 minified 函数体按顶层逗号/分号断行，便于阅读。"""
import sys

path = sys.argv[1]
s = open(path, encoding="utf-8", errors="replace").read()

out = []
i = 0
n = len(s)
depth = 0
while i < n:
    c = s[i]
    if c in "'\"":
        q = c
        out.append(c)
        i += 1
        while i < n:
            out.append(s[i])
            if s[i] == "\\":
                out.append(s[i + 1])
                i += 2
                continue
            if s[i] == q:
                i += 1
                break
            i += 1
        continue
    if c in "([{":
        depth += 1
    elif c in ")]}":
        depth -= 1
    out.append(c)
    if depth <= 1 and c in ",;":
        out.append("\n")
    i += 1

txt = "".join(out)
print(txt)
