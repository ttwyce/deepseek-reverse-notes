# -*- coding: utf-8 -*-
"""诊断 Turnstile widget：sitekey、iframe、自动解出耗时、失败原因。

用法：python tools\\pw_turnstile_diag.py [--show]
"""
from __future__ import annotations

import re
import sys

from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PROXY = "http://127.0.0.1:7890"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def main() -> None:
    show = "--show" in sys.argv
    logs: list[str] = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=not show, args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(
            proxy={"server": PROXY}, locale="en-US", timezone_id="Asia/Tokyo",
            viewport={"width": 1280, "height": 900}, user_agent=UA,
        )
        page = ctx.new_page()
        page.on("console", lambda m: logs.append(f"{m.type}: {m.text[:200]}"))
        page.on("pageerror", lambda e: logs.append(f"pageerror: {str(e)[:200]}"))

        page.goto("https://chat.deepseek.com/sign_up", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(6000)
        print("region:", page.evaluate("""() => {const e=document.querySelector('meta[name=region]'); return e?e.content:null;}"""))

        # turnstile 结构
        diag = page.evaluate("""() => {
            const out = {hasObj: typeof window.turnstile};
            try { out.sitekey = document.querySelector('.cf-turnstile')?.getAttribute('data-sitekey') || null; } catch(e){}
            const ifr = Array.from(document.querySelectorAll('iframe')).map(f => f.src || '(no src)');
            out.iframes = ifr;
            const el = document.querySelector('.cf-turnstile');
            out.widgetHtml = el ? el.outerHTML.slice(0, 400) : null;
            out.widgetCount = document.querySelectorAll('.cf-turnstile').length;
            return out;
        }""")
        print("turnstile 诊断:", diag)

        # 轮询 60s 等 token
        tok = ""
        for i in range(60):
            tok = page.evaluate("""() => { try { return (window.turnstile && window.turnstile.getResponse && window.turnstile.getResponse()) || ''; } catch(e){ return ''; } }""")
            if tok:
                print(f"token 在 {i}s 出现，长度={len(tok)}")
                break
            if i % 10 == 9:
                print(f"  {i+1}s 仍无 token；iframe 数={page.evaluate('() => document.querySelectorAll(chr(39)+chr(39)).length') if False else page.evaluate('() => document.querySelectorAll(\"iframe\").length')}")
            page.wait_for_timeout(1000)
        if not tok:
            print("60s 内未自动出 token")
            # 尝试显式 render / execute
            r = page.evaluate("""() => {
                const out = {};
                try {
                    const el = document.querySelector('.cf-turnstile');
                    if (el && window.turnstile) {
                        const k = el.getAttribute('data-sitekey');
                        out.sitekey = k;
                        const id = window.turnstile.render(el, {sitekey: k});
                        out.renderId = id;
                    }
                } catch(e) { out.renderErr = String(e); }
                return out;
            }""")
            print("手动 render 尝试:", r)
            page.wait_for_timeout(12000)
            tok = page.evaluate("""() => { try { return (window.turnstile && window.turnstile.getResponse && window.turnstile.getResponse()) || ''; } catch(e){ return ''; } }""")
            print("render 后 token 长度:", len(tok))

        print("\n=== console 日志（尾部 25 条）===")
        for l in logs[-25:]:
            print("  ", l)

        page.screenshot(path="work/pw_turnstile.png", full_page=False)
        print("[截图] work/pw_turnstile.png")
        b.close()


if __name__ == "__main__":
    main()
