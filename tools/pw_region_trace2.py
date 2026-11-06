# -*- coding: utf-8 -*-
"""地区判定溯源 v2：抓全部请求（含第三方）+ settings 响应 + React 内 isMainlandChina 值。

用法：python tools\\pw_region_trace2.py
"""
from __future__ import annotations

import json
import sys

from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PROXY = "http://127.0.0.1:7890"


def main() -> None:
    reqs: list[str] = []
    resp_bodies: dict[str, str] = {}

    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(
            proxy={"server": PROXY}, locale="en-US", timezone_id="Asia/Tokyo",
            viewport={"width": 1280, "height": 900},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
        )
        page = ctx.new_page()
        page.on("request", lambda r: reqs.append(f"{r.method} {r.url[:170]}"))

        def on_resp(r):
            u = r.url
            if "/api/v0/client/settings" in u or "/ip" in u or "ipify" in u or "ipinfo" in u or "geo" in u.lower():
                try:
                    resp_bodies[u[:170]] = r.text()[:500]
                except Exception:
                    pass

        page.on("response", on_resp)
        page.goto("https://chat.deepseek.com/sign_up", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(5000)

        print("=== 全部请求（去重）===")
        for u in dict.fromkeys(reqs):
            print(" ", u)

        print("\n=== 相关响应体 ===")
        for u, body in resp_bodies.items():
            print(f"\n[{u}]\n{body}")

        # LocalStorage / sessionStorage 里的地区线索
        print("\n=== storage ===")
        st = page.evaluate("""() => {
            const out = {};
            for (const s of [localStorage, sessionStorage]) {
                for (let i=0;i<s.length;i++){ const k=s.key(i); if(/ip|region|mainland|country|geo|locale/i.test(k)) out[k]=String(s.getItem(k)).slice(0,120); }
            }
            return out;
        }""")
        print(json.dumps(st, ensure_ascii=False))
        b.close()


if __name__ == "__main__":
    main()
