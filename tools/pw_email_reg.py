# -*- coding: utf-8 -*-
"""境外 IP 下用浏览器完成「发送邮箱验证码」，并保存会话供下一步提交注册。

用法：
  python tools\\pw_email_reg.py send              # 发码（会真的发邮件）
  python tools\\pw_email_reg.py send --email a@b.c

产物：work\\email_reg_state.json（storage_state）、work\\email_reg_send.json（发码响应）
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PROXY = "http://127.0.0.1:7890"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
STATE = Path("work/email_reg_state.json")
SEND_OUT = Path("work/email_reg_send.json")
DEFAULT_EMAIL = "demo.user+4@example.com"


def main() -> None:
    email = DEFAULT_EMAIL
    if "--email" in sys.argv:
        email = sys.argv[sys.argv.index("--email") + 1]

    captured: list[dict] = []

    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(
            proxy={"server": PROXY}, locale="en-US", timezone_id="Asia/Tokyo",
            viewport={"width": 1280, "height": 900}, user_agent=UA,
        )

        def on_resp(r):
            if "create_email_verification_code" in r.url or "/users/register" in r.url:
                try:
                    captured.append({"url": r.url, "status": r.status, "body": r.text()[:1500]})
                except Exception as e:
                    captured.append({"url": r.url, "status": r.status, "body": f"<read fail {e}>"})

        page = ctx.new_page()
        page.on("response", on_resp)
        page.goto("https://chat.deepseek.com/sign_up", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)
        print("region:", page.evaluate("""() => {const e=document.querySelector('meta[name=region]'); return e?e.content:null;}"""))

        # 填邮箱
        page.fill('input[placeholder="Email address"]', email)
        page.wait_for_timeout(800)
        print("已填邮箱:", email)

        # 等 turnstile 自动出 token（最多 20s）
        tok = ""
        for i in range(20):
            tok = page.evaluate("""() => {
                try { return (window.turnstile && window.turnstile.getResponse && window.turnstile.getResponse()) || ''; }
                catch(e) { return ''; }
            }""")
            if tok:
                print(f"turnstile token 已就绪（第{i+1}次轮询，长度 {len(tok)}）")
                break
            page.wait_for_timeout(1000)
        if not tok:
            print("turnstile 未自动出 token（可能需交互）")

        # 点 Send code
        clicked = page.evaluate("""() => {
            const cand = Array.from(document.querySelectorAll('button,div[role=button],span'));
            const t = cand.find(e => /^\\s*send code\\s*$/i.test((e.innerText||'').trim()));
            if (t) { t.click(); return (t.innerText||'').trim(); }
            return null;
        }""")
        print("点击 Send code ->", clicked)
        page.wait_for_timeout(8000)

        print("\n=== 抓到的接口响应 ===")
        for c in captured:
            print(f"[{c['status']}] {c['url'][:110]}")
            print("   ", c["body"].replace("\n", " ")[:800])

        # 页面当前提示
        try:
            body_txt = page.inner_text("body")[:500]
            print("\n=== 页面文案(前500) ===\n", body_txt)
        except Exception:
            pass

        ctx.storage_state(path=str(STATE))
        SEND_OUT.write_text(json.dumps(captured, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\n[storage_state] {STATE}\n[发码响应] {SEND_OUT}")
        page.screenshot(path="work/pw_email_send.png", full_page=True)
        print("[截图] work/pw_email_send.png")
        b.close()


if __name__ == "__main__":
    main()
