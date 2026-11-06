# -*- coding: utf-8 -*-
"""境外 IP 下的 WAF 挑战分析 + 浏览器过挑战取 region。

用法：python tools\\geo_field_probe3.py
"""
from __future__ import annotations

import re
import sys

import requests
from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PROXY = "http://127.0.0.1:7890"
PROXIES = {"http": PROXY, "https": PROXY}
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def raw_probe() -> None:
    print("=== ① requests 经代理 GET /sign_up ===")
    s = requests.Session()
    s.trust_env = False
    r = s.get("https://chat.deepseek.com/sign_up",
              headers={"user-agent": UA, "accept": "text/html,application/xhtml+xml,*/*;q=0.8",
                       "accept-language": "en-US,en;q=0.9"},
              proxies=PROXIES, timeout=30, allow_redirects=False)
    print("status:", r.status_code)
    for k, v in r.headers.items():
        if k.lower() in ("server", "set-cookie", "content-type", "location", "content-length"):
            print(f"  {k}: {v[:200]}")
    body = r.text
    print("body len:", len(body))
    print("body[:1200] >>>")
    print(body[:1200].replace("\r", ""))
    print("<<<")
    for pat in (r'meta name="ip" content="([^"]*)"', r'meta name="region" content="([^"]*)"',
                r'window\._waf', r'HWWAF', r'challenge'):
        m = re.search(pat, body, re.I)
        print(f"  [{pat}] -> {m.group(0)[:120] if m else None}")


def browser_probe() -> None:
    print("\n=== ② Playwright 经代理打开 /sign_up（可执行 JS 挑战）===")
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        ctx = b.new_context(
            proxy={"server": PROXY}, locale="en-US", timezone_id="Asia/Tokyo",
            viewport={"width": 1280, "height": 900}, user_agent=UA,
        )
        page = ctx.new_page()
        try:
            page.goto("https://chat.deepseek.com/sign_up", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(6000)
            print("url:", page.url)
            print("title:", page.title())
            meta = page.evaluate("""() => {
                const g = n => { const e = document.querySelector(`meta[name="${n}"]`); return e ? e.content : null; };
                return {ip: g('ip'), region: g('region')};
            }""")
            print("meta:", meta)
            body_text = page.inner_text("body")[:600] if page.query_selector("body") else ""
            print("body text >>>\n", body_text, "\n<<<")
            inputs = page.evaluate("""() => Array.from(document.querySelectorAll('input')).map(i => ({type:i.type, name:i.name, ph:i.placeholder, id:i.id}))""")
            print("inputs:", inputs)
            print("turnstile:", page.evaluate("() => typeof window.turnstile"))
            print("cookies:", [f"{c['name']}={c['value'][:24]}" for c in ctx.cookies()])
            page.screenshot(path="work/pw_global_signup.png", full_page=True)
            print("[截图] work/pw_global_signup.png")
        except Exception as e:
            print("FAIL:", type(e).__name__, e)
        b.close()


if __name__ == "__main__":
    raw_probe()
    browser_probe()
