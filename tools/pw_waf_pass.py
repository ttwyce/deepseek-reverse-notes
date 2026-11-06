# -*- coding: utf-8 -*-
"""境外 IP 下通过 AWS WAF 人机验证，并导出可复用的 aws-waf-token。

用法：
  python tools\\pw_waf_pass.py            # 无头尝试
  python tools\\pw_waf_pass.py --show     # 有头（失败时观察用）

产物：work\\waf_state.json（含 storage_state，供后续 requests/Playwright 复用）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PROXY = "http://127.0.0.1:7890"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
STATE = Path("work/waf_state.json")


def info(page) -> dict:
    return page.evaluate("""() => {
        const g = n => { const e = document.querySelector(`meta[name="${n}"]`); return e ? e.content : null; };
        return {
            ip: g('ip'), region: g('region'),
            title: document.title,
            nInputs: document.querySelectorAll('input').length,
            hasBegin: Array.from(document.querySelectorAll('button,a,div[role=button]'))
                        .some(e => /begin/i.test(e.innerText || '')),
        };
    }""")


def main() -> None:
    show = "--show" in sys.argv
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=not show, args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(
            proxy={"server": PROXY}, locale="en-US", timezone_id="Asia/Tokyo",
            viewport={"width": 1280, "height": 900}, user_agent=UA,
        )
        page = ctx.new_page()
        page.goto("https://chat.deepseek.com/sign_up", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)
        print("初始:", json.dumps(info(page), ensure_ascii=False))

        # 点 Begin（若存在）
        for attempt in range(3):
            clicked = page.evaluate("""() => {
                const cand = Array.from(document.querySelectorAll('button,a,div[role=button]'));
                const t = cand.find(e => /begin/i.test((e.innerText||'').trim()));
                if (t) { t.click(); return true; }
                return false;
            }""")
            print(f"  第{attempt+1}次点 Begin -> {clicked}")
            page.wait_for_timeout(7000)
            st = info(page)
            print("  状态:", json.dumps(st, ensure_ascii=False))
            if st.get("region") == "overseas" or (st.get("nInputs") or 0) > 0:
                print("  >>> 已进入正常页面")
                break

        page.wait_for_timeout(3000)
        st = info(page)
        print("\n最终:", json.dumps(st, ensure_ascii=False))
        print("url:", page.url)
        cookies = ctx.cookies()
        for c in cookies:
            print(f"  cookie {c['name']} (len={len(c['value'])}) domain={c['domain']}")
        page.screenshot(path="work/pw_waf_result.png", full_page=True)
        print("[截图] work/pw_waf_result.png")

        ctx.storage_state(path=str(STATE))
        print(f"[storage_state] {STATE}")

        # 若进入正常页，顺便 dump 注册页表单
        if (st.get("nInputs") or 0) > 0:
            txt = page.inner_text("body")[:800]
            print("\n=== 页面文案 ===\n", txt)
            inputs = page.evaluate("""() => Array.from(document.querySelectorAll('input')).map(i=>({type:i.type,name:i.name,ph:i.placeholder}))""")
            print("inputs:", inputs)
            print("turnstile:", page.evaluate("() => typeof window.turnstile"))
        b.close()


if __name__ == "__main__":
    main()
