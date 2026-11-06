# -*- coding: utf-8 -*-
"""网页端注册页探测：经日本代理打开 chat.deepseek.com 注册页，
抓 DOM 结构 / Turnstile iframe / 真实发码请求体。

用法：python tools\\pw_signup_probe.py [headless]
"""
from __future__ import annotations

import json
import os
import sys

from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

WORK = r"F:\dshh\deepseeka\work"
PROXY = "http://127.0.0.1:7890"
HITS: list[dict] = []


def on_request(req):
    u = req.url
    if "/api/v0/users/" in u or "challenges.cloudflare.com" in u:
        body = None
        try:
            body = req.post_data
        except Exception:
            pass
        HITS.append({"method": req.method, "url": u[:160], "body": (body or "")[:600]})


def main() -> None:
    headless = not (len(sys.argv) > 1 and sys.argv[1] == "head")
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=headless, args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(
            proxy={"server": PROXY},
            locale="en-US",
            timezone_id="Asia/Tokyo",
            viewport={"width": 1280, "height": 900},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
        )
        page = ctx.new_page()
        page.on("request", on_request)
        for path in ("/sign_up", "/sign_in"):
            print(f"\n=== {path} ===")
            try:
                page.goto("https://chat.deepseek.com" + path, wait_until="domcontentloaded", timeout=45000)
            except Exception as e:
                print("goto 失败:", e)
                continue
            page.wait_for_timeout(9000)
            print("url   :", page.url)
            print("title :", page.title())
            txt = page.inner_text("body")[:900]
            print("body  :", " | ".join(txt.split("\n"))[:700])
            # Turnstile widget 探测
            info = page.evaluate("""() => {
                const ifr = [...document.querySelectorAll('iframe')].map(f => f.src.slice(0,120));
                const inp = [...document.querySelectorAll('input')].map(i => i.name || i.type);
                const ts = document.querySelectorAll('[name="cf-turnstile-response"]').length;
                const labels = [...document.querySelectorAll('button,div[role=button],a')]
                    .map(e => (e.innerText||'').trim()).filter(Boolean).slice(0, 25);
                return {iframes: ifr, inputs: inp, turnstile_resp: ts,
                        has_turnstile: typeof window.turnstile, labels};
            }""")
            print("probe :", json.dumps(info, ensure_ascii=False)[:800])
            shot = os.path.join(WORK, f"pw_signup{path.replace('/', '_')}.png")
            page.screenshot(path=shot, full_page=True)
            print("shot  :", shot)

        print("\n=== 捕获的接口请求 ===")
        for h in HITS:
            print(f"{h['method']} {h['url']}")
            if h["body"]:
                print("   body:", h["body"])
        b.close()


if __name__ == "__main__":
    main()
