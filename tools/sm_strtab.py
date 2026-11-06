"""还原数美 captcha-sdk 的 obfuscator 字符串表。
原理：_0x3634(idx) = strArray[idx - 0x1AF]，随后一个 IIFE 通过校验和旋转数组。
把「数组函数 + 解码函数 + 旋转 IIFE」单独放进浏览器执行，导出完整字符串表，
再把整份 SDK 的 _0xXXXX(0xNNN) 调用就地替换成明文字符串。
"""
import json
import os
import re

from playwright.sync_api import sync_playwright

SRC = r"work\sm\captcha-sdk.min.js"
OUT = r"work\sm"
raw = open(SRC, encoding="utf-8", errors="replace").read()
s = "".join(c if (c.isprintable() or c == "\n") else " " for c in raw)

# header = 字符串数组函数 + 解码函数 + 旋转 IIFE（精确到 IIFE 的右括号）
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


anchor = s.index("}(_0x127b,")
open_paren = s.index("(function(_0x21dad6")   # 外层逗号表达式起点
close = match_paren(s, open_paren)
header = s[: close + 1]
print("[header]", len(header), "chars; tail:", header[-40:].encode("ascii", "replace").decode())
print("[header]", len(header), "chars; tail:", header[-60:].encode("ascii", "replace").decode())

JS = header + r"""
;(function(){
  try {
    if (typeof _0x3634 !== 'function') { window.__ERR__ = 'no decoder'; return; }
    var tab = {};
    for (var i = 0x1af; i < 0x1af + 4000; i++) {
      try { var v = _0x3634(i); if (typeof v === 'string') tab[i] = v; } catch (e) { break; }
    }
    window.__STRTAB__ = tab;
  } catch (e) { window.__ERR__ = String(e && e.stack || e); }
})();
"""

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    pg = b.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("about:blank")
    try:
        pg.add_script_tag(content=JS)
    except Exception as e:
        print("[add_script_tag failed]", e)
    tab = pg.evaluate("() => window.__STRTAB__ || {}")
    diag = pg.evaluate("() => ({err: window.__ERR__ || null, t: typeof _0x3634})")
    print("[diag]", diag, "pageerrors:", errs[:3])
    b.close()

print("[strtab] entries:", len(tab))
with open(os.path.join(OUT, "strtab.json"), "w", encoding="utf-8") as fh:
    json.dump(tab, fh, ensure_ascii=False, indent=0)

if tab:
    DECODERS = ["_0x3634", "_0x117065", "_0x408168", "_0x13e36d", "_0x331fa1", "_0x1f631c"]
    cnt = [0]

    def make(dec):
        def repl(mo2):
            idx = int(mo2.group(1), 16)
            if str(idx) in tab:
                cnt[0] += 1
                return json.dumps(tab[str(idx)], ensure_ascii=False)
            return mo2.group(0)
        return repl

    for dec in DECODERS:
        s = re.sub(re.escape(dec) + r"\((0x[0-9a-fA-F]+)\)", make(dec), s)
    print("[replace] 替换调用数:", cnt[0])
    with open(os.path.join(OUT, "captcha-sdk.deob.js"), "w", encoding="utf-8") as fh:
        fh.write(s)
    print("[out] work/sm/captcha-sdk.deob.js", len(s))
