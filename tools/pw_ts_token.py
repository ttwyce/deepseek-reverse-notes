# -*- coding: utf-8 -*-
"""在页面里手动渲染 Turnstile，取真 token。

用法：python tools\\pw_ts_token.py [--hl]
  默认有头（headless=False），更易通过 Cloudflare 检测。
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
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
SITEKEY = "0x4AAAAAAA1jQEh8YFk064tz"


def main() -> None:
    hl = "--hl" in sys.argv
    with sync_playwright() as p:
        b = p.chromium.launch(headless=hl, args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(proxy={"server": PROXY}, locale="en-US", timezone_id="Asia/Tokyo",
                            viewport={"width": 1280, "height": 900}, user_agent=UA)
        page = ctx.new_page()
        logs: list[str] = []
        page.on("console", lambda m: logs.append(f"{m.type}: {m.text[:160]}"))
        page.goto("https://chat.deepseek.com/sign_up", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)
        print("region:", page.evaluate("()=>{const e=document.querySelector('meta[name=region]');return e?e.content:null}"))
        print("turnstile:", page.evaluate("()=>typeof window.turnstile"))

        # 自建容器并 render
        r = page.evaluate(
            """(sk) => {
                try {
                    let d = document.getElementById('my-ts');
                    if (!d) { d = document.createElement('div'); d.id='my-ts';
                              d.style.cssText='position:fixed;left:10px;top:10px;z-index:999999;background:#fff;padding:8px';
                              document.body.appendChild(d); }
                    window.__tsTok = '';
                    window.__tsErr = '';
                    window.__tsId = window.turnstile.render('#my-ts', {
                        sitekey: sk,
                        callback: (t) => { window.__tsTok = t; },
                        'error-callback': (c) => { window.__tsErr = String(c); },
                        'timeout-callback': () => { window.__tsErr = 'timeout'; }
                    });
                    return {ok: true, id: String(window.__tsId)};
                } catch (e) { return {ok: false, err: String(e)}; }
            }""",
            SITEKEY,
        )
        print("render 结果:", r)

        tok = ""
        for i in range(75):
            page.wait_for_timeout(1000)
            st = page.evaluate("()=>({tok: window.__tsTok || '', err: window.__tsErr || '', ifr: document.querySelectorAll('iframe').length})")
            if st["tok"]:
                tok = st["tok"]
                print(f"[{i+1}s] 拿到 token 长度={len(tok)}")
                break
            if i % 10 == 9:
                print(f"  [{i+1}s] err={st['err']!r} iframes={st['ifr']}")

        if tok:
            print("token 前 60:", tok[:60])
            print("token 全字段:", page.evaluate("()=>{try{return JSON.stringify(window.turnstile.getResponse())}catch(e){return ''}}")[:200])
            with open("work/ts_token.json", "w", encoding="utf-8") as f:
                json.dump({"token": tok, "sitekey": SITEKEY}, f, ensure_ascii=False, indent=2)
            print("[保存] work/ts_token.json")
        else:
            print("未拿到 token", page.evaluate("()=>window.__tsErr"))

        print("\n=== console 尾部 15 ===")
        for l in logs[-15:]:
            print("  ", l)
        page.screenshot(path="work/pw_ts_token.png")
        b.close()


if __name__ == "__main__":
    main()
