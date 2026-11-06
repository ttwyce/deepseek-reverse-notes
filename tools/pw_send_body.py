# -*- coding: utf-8 -*-
"""抓发码请求的完整 POST body + overlay/iframe 出现情况 + turnstile token 状态。"""
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
                captured.append({"url": req.url, "method": req.method,
                                 "headers": dict(req.headers), "body": req.post_data})

        page.on("request", on_req)

        page.goto("https://chat.deepseek.com/sign_up", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(7000)
        print("region:", page.evaluate("()=>{const e=document.querySelector('meta[name=region]');return e?e.content:null}"))

        page.fill("input[type=text]", EMAIL)
        print("已填邮箱")

        # 点击前快照
        pre = page.evaluate("""()=>({overlay: !!document.querySelector('#cf-overlay'),
            ts: !!document.querySelector('#cf-turnstile'), iframes: document.querySelectorAll('iframe').length})""")
        print("点击前 DOM:", pre)

        # 点 Send code
        btn = page.get_by_text("Send code", exact=True).first
        btn.click()
        print("已点击 Send code")

        # 点后轮询 20s，观察 overlay/iframe/token
        for i in range(20):
            page.wait_for_timeout(1000)
            st = page.evaluate("""()=>{
                const ov = document.querySelector('#cf-overlay');
                let tok = '';
                try { tok = (window.turnstile && window.turnstile.getResponse && window.turnstile.getResponse()) || ''; } catch(e){}
                return {overlay: !!ov, overlayDisplay: ov ? ov.style.display : null,
                    ts: !!document.querySelector('#cf-turnstile'), widgetCount: document.querySelectorAll('.cf-turnstile').length,
                    iframes: Array.from(document.querySelectorAll('iframe')).map(f=>f.src?f.src.slice(0,120):'');
                    tokLen: tok.length, captured: null};
            }""")
            print(f"  {i+1}s", st)
            if captured:
                break

        page.screenshot(path="work/pw_send_body.png")
        print("\n=== 捕获请求 ===")
        for c in captured:
            print("URL:", c["url"])
            print("HEADERS:", json.dumps(c["headers"], ensure_ascii=False, indent=2))
            print("BODY:", c["body"])
            try:
                j = json.loads(c["body"] or "{}")
                print("\n字段分析:")
                for k, v in j.items():
                    print(f"  {k} = {v!r}")
            except Exception as e:
                print("body 解析失败", e)
        if not captured:
            print("(未捕获)")
        b.close()


if __name__ == "__main__":
    main()
