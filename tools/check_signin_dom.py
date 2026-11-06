# -*- coding: utf-8 -*-
"""自检：确认 chat.deepseek.com/sign_in 的 DOM 结构仍与 login_page.py 的假设一致。

不提交任何登录请求，只加载页面并检查选择器。
用法：.\\\\.venv\\\\Scripts\\\\python.exe tools\\\\check_signin_dom.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(r"F:\dshh\deepseeka")
WORK = ROOT / "work"
CHROME = ROOT / "tools" / "pw-browsers" / "chromium-1248" / "chrome-win64" / "chrome.exe"
SIGN_IN = "https://chat.deepseek.com/sign_in"

CAPTCHA_SELECTORS = [
    '[class*="sm-captcha"]', "#sm-captcha", ".sm-captcha-wrap",
    '[id*="sm-captcha"]', 'iframe[src*="captcha"]', 'iframe[src*="shumei"]',
    '[class*="captcha"]', '[id*="captcha"]',
]

CODE_SELECTORS = [
    'input[placeholder*="验证码"]', 'input[placeholder*="邮箱验证码"]',
    'input[name*="code"]', 'input[maxlength="6"]',
]


def main() -> int:
    ok = True
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path=str(CHROME) if CHROME.exists() else None,
            args=["--disable-blink-features=AutomationControlled", "--no-first-run"],
        )
        ctx = browser.new_context(
            locale="zh-CN", timezone_id="Asia/Shanghai",
            viewport={"width": 1280, "height": 900},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"),
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = ctx.new_page()
        page.goto(SIGN_IN, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3500)

        print("title       :", page.title())
        print("url         :", page.url)

        def has(sel: str) -> bool:
            try:
                return page.query_selector(sel) is not None
            except Exception:  # noqa: BLE001
                return False

        email_ok = has("input[placeholder*='手机号/邮箱']")
        pwd_ok = has("input[type=password]")
        print("邮箱/手机输入框 :", email_ok)
        print("密码输入框      :", pwd_ok)
        if not (email_ok and pwd_ok):
            ok = False
            print("  !! 输入框选择器失配")

        # 检查「密码登录」tab 文本
        tab_text = page.evaluate("""() => {
            const out = [];
            for (const el of document.querySelectorAll('.ds-button__content, button')) {
                const t = (el.textContent || '').replace(/\\s+/g, '');
                if (t && t.length <= 10) out.push(t);
            }
            return out;
        }""")
        print("按钮文本        :", tab_text)
        if "密码登录" not in tab_text:
            ok = False
            print("  !! 没找到「密码登录」tab")

        # 初始页面不应有验证码
        found = []
        for sel in CAPTCHA_SELECTORS:
            try:
                n = len(page.query_selector_all(sel))
            except Exception:  # noqa: BLE001
                n = -1
            if n:
                found.append((sel, n))
        print("初始验证码元素  :", found or "无（符合预期）")

        print("验证码输入框    :", [s for s in CODE_SELECTORS if has(s)] or "无（符合预期）")

        WORK.mkdir(parents=True, exist_ok=True)
        shot = WORK / "signin_dom_check.png"
        page.screenshot(path=str(shot), full_page=False)
        print("截图            :", shot)

        browser.close()

    print("\n结论:", "DOM 结构符合 login_page.py 的假设" if ok else "有选择器失配，需修正")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
