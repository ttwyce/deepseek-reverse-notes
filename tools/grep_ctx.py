# -*- coding: utf-8 -*-
"""在 bundle 里按正则打印上下文片段。

用法：python tools\\grep_ctx.py <regex> [<regex2> ...] [--file=path] [--pad=260] [--max=12]
"""
from __future__ import annotations

import re
import sys


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opts = {a.split("=", 1)[0][2:]: a.split("=", 1)[1] for a in sys.argv[1:] if "=" in a and a.startswith("--")}
    path = opts.get("file", r"work\main_web.js")
    pad = int(opts.get("pad", "260"))
    mx = int(opts.get("max", "12"))

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    s = open(path, encoding="utf-8", errors="replace").read()
    print(f"[file] {path} len={len(s)}")
    for pat in args:
        print(f"\n===== {pat}")
        seen: set[str] = set()
        for m in re.finditer(pat, s):
            a, b = max(0, m.start() - pad), min(len(s), m.end() + pad)
            frag = s[a:b].replace("\n", " ")
            key = frag[:80]
            if key in seen:
                continue
            seen.add(key)
            print(f"--- @{m.start()}")
            print(frag)
            if len(seen) >= mx:
                print(f"... (capped at {mx})")
                break
        if not seen:
            print("(no match)")


if __name__ == "__main__":
    main()
