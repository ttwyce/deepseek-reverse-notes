"""定位 pretty 文件中某行起始 IIFE 的配对结束位置，并打印随后的实参代码。"""
import sys

PATH = r"work\sm\fp.min.pretty.js"
line_no = int(sys.argv[1]) if len(sys.argv) > 1 else 848
tail = int(sys.argv[2]) if len(sys.argv) > 2 else 60

text = open(PATH, encoding="utf-8").read()
lines = text.split("\n")
start = sum(len(l) + 1 for l in lines[:line_no - 1])

depth = 0
i = start
n = len(text)
started = False
while i < n:
    c = text[i]
    if c in "'\"":
        q = c
        j = i + 1
        while j < n:
            if text[j] == "\\":
                j += 2
                continue
            if text[j] == q:
                break
            j += 1
        i = j + 1
        continue
    if c in "([{":
        depth += 1
        started = True
    elif c in ")]}":
        depth -= 1
        if started and depth == 0:
            break
    i += 1

end_line = text[:i].count("\n") + 1
print(f"[IIFE] starts line {line_no}, closes at char {i}, line {end_line}")
print("---- tail of IIFE body (last 1500 chars) ----")
print(text[max(start, i - 1500):i + 1])
print("---- following args (1200 chars) ----")
print(text[i + 1:i + 1201])
