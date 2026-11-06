# -*- coding: utf-8 -*-
"""注册页地区判定溯源：抓全部网络请求 + cookie/localStorage + bundle 文案定位。

用法：python tools\\pw_region_trace.py
"""
from __future__ import annotations

import json
import re
import sys

from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PROXY = "http://127.0.0.1:7890"
REQS: list[str] = []
DOCS: dict[str, str] = {}
NEEDLE = "Only phone number registration is supported"


def main() -> None:
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(
            proxy={"server": PROXY}, locale="en-US", timezone_id="Asia/Tokyo",
            viewport={"width": 1280, "height": 900},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
        )
        page = ctx.new_page()

        def on_req(r):
            u = r.url
            if "chat.deepseek.com" in u or "deepseek" in u:
                REQS.append(f"{r.method} {u[:150]}")

        def on_resp(r):
            u = r.url
            if u.endswith(".js") or ".js?" in u:
                try:
                    body = r.text()
                    if NEEDLE in body:
                        DOCS[u] = body
                except Exception:
                    pass

        page.on("request", on_req)
        page.on("response", on_resp)
        page.goto("https://chat.deepseek.com/sign_up", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(4000)

        print("=== 请求清单 ===")
        for u in dict.fromkeys(REQS):
            print(" ", u)

        print("\n=== cookie ===")
        for c in ctx.cookies():
            print(f"  {c['name']} = {c['value'][:60]}  (domain={c['domain']})")

        print("\n=== 含目标文案的 bundle ===")
        print(" ", list(DOCS.keys()))

        for url, body in DOCS.items():
            idx = body.find(NEEDLE)
            print(f"\n--- {url} @ {idx} ---")
            seg = body[max(0, idx - 1200): idx + 400]
            for m in re.finditer(r"[\w$]{1,24}=[^,;{}]{0,80}", seg):
                pass
            print(seg[-1400:])
        b.close()


if __name__ == "__main__":
    main()
