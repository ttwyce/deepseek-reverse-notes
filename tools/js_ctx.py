"""按 needle 打印任意文本文件中的上下文片段。

用法：python tools/js_ctx.py <file> <needle> [width=400] [maxhits=6]
"""
import sys
from pathlib import Path


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    path = Path(sys.argv[1])
    needle = sys.argv[2]
    width = int(sys.argv[3]) if len(sys.argv) > 3 else 400
    maxhits = int(sys.argv[4]) if len(sys.argv) > 4 else 6
    s = path.read_text(encoding="utf-8", errors="replace")
    pos, n = 0, 0
    while True:
        i = s.find(needle, pos)
        if i < 0:
            break
        n += 1
        a = max(0, i - width // 2)
        b = min(len(s), i + width // 2)
        print(f"\n=== hit {n} @ {i} ===")
        print(s[a:b].replace("\n", " "))
        pos = i + len(needle)
        if n >= maxhits:
            break
    print(f"\ntotal shown: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
