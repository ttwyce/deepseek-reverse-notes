# -*- coding: utf-8 -*-
"""抓发码请求的原始 body（bytes）+ header，判断编码方式。"""
from __future__ import annotations

import json
import sys

from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PROXY = "http://127.0.0.1:7890"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
EMAIL = "demo.user+4@example.com"

captured: list[dict] = []


def hexdump(b: bytes, n: int = 160) -> str:
    b = b[:n]
    lines = []
    for i in range(0, len(b), 16):
        chunk = b[i:i + 16]
        hx = " ".join(f"{c:02x}" for c in chunk)
        asc = "".join(chr(c) if 32 <= c < 127 else "." for c in chunk)
        lines.append(f"{i:04x}  {hx:<48}  {asc}")
    return "\n".join(lines)


def main() -> None:
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(
            proxy={"server": PROXY}, locale="en-US", timezone_id="Asia/Tokyo",
            viewport={"width": 1280, "height": 900}, user_agent=UA,
        )
        page = ctx.new_page()

        def on_req(req):
            if "create_email_verification_code" in req.url:
                try:
                    buf = req.post_data_buffer
                except Exception as e:
                    buf = b""
                    print("post_data_buffer 失败:", e)
                captured.append({"url": req.url, "method": req.method,
                                 "headers": dict(req.headers), "buf": buf})

        page.on("request", on_req)

        page.goto("https://chat.deepseek.com/sign_up", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(7000)
        print("region:", page.evaluate("()=>{const e=document.querySelector('meta[name=region]');return e?e.content:null}"))

        page.fill("input[type=text]", EMAIL)
        page.get_by_text("Send code", exact=True).first.click()
        print("已点击 Send code，等待...")
        for _ in range(15):
            page.wait_for_timeout(1000)
            if captured:
                break

        print("\n=== 捕获 ===")
        for c in captured:
            print("URL:", c["url"])
            h = c["headers"]
            for k in ("content-type", "content-encoding", "content-length", "accept"):
                if k in h:
                    print(f"  {k}: {h[k]}")
            buf = c["buf"]
            print(f"body 长度: {len(buf)}")
            print(hexdump(buf))
            # 尝试常见解压
            for name, fn in (
                ("gzip", lambda x: __import__("gzip").decompress(x)),
                ("zlib", lambda x: __import__("zlib").decompress(x)),
                ("zstd", lambda x: __import__("zstandard").decompress(x)),
            ):
                try:
                    out = fn(buf)
                    print(f"  [{name} 解压成功] {out[:500]!r}")
                    break
                except Exception:
                    pass
        if not captured:
            print("(未捕获)")
        b.close()


if __name__ == "__main__":
    main()
