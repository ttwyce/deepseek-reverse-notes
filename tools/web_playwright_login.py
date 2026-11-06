# -*- coding: utf-8 -*-
"""用真实 Chromium 完成 DeepSeek 网页登录，取出 token。

用途：纯协议在服务端 `biz_code 11 RISK_DEVICE_DETECTED` 处被拦，真实浏览器环境是唯一能
让风控放行的路径。登录成功后的 token 可直接供纯协议调用 /api/v0/* 使用。

用法：
    set PLAYWRIGHT_BROWSERS_PATH=F:\\dshh\\deepseeka\\tools\\pw-browsers
    .venv\\Scripts\\python.exe tools\\web_playwright_login.py [--headless] [--wait 180]
"""
from __future__ import annotations
# --- credentials: 从环境变量或本地 local_config.py 读取（local_config 不入库）---
import os as _os


def _cred(key, default=""):
    v = _os.environ.get(key)
    if v:
        return v
    try:
        from local_config import CFG  # type: ignore
        return CFG.get(key, default)
    except Exception:
        return default



import argparse
import json
import os
import time

from playwright.sync_api import sync_playwright

EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")
SIGN_IN = "https://chat.deepseek.com/sign_in"
WORK = r"F:\dshh\deepseeka\work"
STATE = os.path.join(WORK, "pw_state.json")
SHOT = os.path.join(WORK, "pw_login.png")


def dump_storage(page) -> dict:
    data = page.evaluate("""() => {
        const out = {local: {}, session: {}, cookie: document.cookie};
        try { for (let i = 0; i < localStorage.length; i++) {
            const k = localStorage.key(i); out.local[k] = localStorage.getItem(k); } } catch (e) {}
        try { for (let i = 0; i < sessionStorage.length; i++) {
            const k = sessionStorage.key(i); out.session[k] = sessionStorage.getItem(k); } } catch (e) {}
        return out;
    }""")
    return data


def find_token(storage: dict) -> list[str]:
    keys = []
    for scope in ("local", "session"):
        for k, v in (storage.get(scope) or {}).items():
            if not isinstance(v, str):
                continue
            low = k.lower()
            if "token" in low or "auth" in low or "user" in low:
                keys.append(f"{scope}:{k} = {v[:120]}")
            elif v.startswith("{"):
                try:
                    obj = json.loads(v)
                    if isinstance(obj, dict) and any(
                            t in obj for t in ("token", "value", "userToken")):
                        keys.append(f"{scope}:{k} = {v[:200]}")
                except Exception:  # noqa: BLE001
                    pass
    return keys


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--wait", type=int, default=180,
                    help="登录后等待秒数（留时间人工过验证码）")
    args = ap.parse_args()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=args.headless, args=[
            "--disable-blink-features=AutomationControlled",
            "--no-first-run",
        ])
        ctx = browser.new_context(
            viewport={"width": 1366, "height": 900},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
        page = ctx.new_page()

        print("open", SIGN_IN)
        page.goto(SIGN_IN, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)
        page.screenshot(path=SHOT)
        print("title:", page.title())

        # 尝试填表：优先 placeholder / input[type]
        filled = False
        for sel in ["input[type=email]", "input[name=email]",
                    "input[placeholder*='mail']", "input[placeholder*='邮箱']"]:
            try:
                if page.locator(sel).count() > 0:
                    page.fill(sel, EMAIL, timeout=5000)
                    filled = True
                    print("filled email via", sel)
                    break
            except Exception:  # noqa: BLE001
                continue
        for sel in ["input[type=password]", "input[name=password]"]:
            try:
                if page.locator(sel).count() > 0:
                    page.fill(sel, PASSWORD, timeout=5000)
                    print("filled password via", sel)
                    break
            except Exception:  # noqa: BLE001
                continue

        if filled:
            for sel in ["button[type=submit]", "button:has-text('登录')",
                        "button:has-text('Log in')", "div[role=button]:has-text('登录')"]:
                try:
                    if page.locator(sel).count() > 0:
                        page.click(sel, timeout=5000)
                        print("clicked", sel)
                        break
                except Exception:  # noqa: BLE001
                    continue

        print(f"waiting up to {args.wait}s (手动过验证码 / 观察跳转) ...")
        deadline = time.time() + args.wait
        last_url = ""
        while time.time() < deadline:
            page.wait_for_timeout(2000)
            url = page.url
            if url != last_url:
                print("url ->", url)
                last_url = url
            if "/sign_in" not in url and "chat.deepseek.com" in url:
                print("似乎已跳转，继续观察 10s 稳定")
                page.wait_for_timeout(10000)
                break

        page.screenshot(path=SHOT)
        storage = dump_storage(page)
        print("\n=== storage keys ===")
        for scope in ("local", "session"):
            for k, v in (storage.get(scope) or {}).items():
                print(f"  {scope}:{k} = {str(v)[:100]}")

        print("\n=== token 候选 ===")
        for line in find_token(storage):
            print("  " + line)

        cookies = ctx.cookies()
        print("\n=== cookies ===")
        for c in cookies:
            print(f"  {c['name']} = {c['value'][:80]} (domain={c['domain']})")

        ctx.storage_state(path=STATE)
        print("\nstorage_state saved:", STATE)
        print("screenshot:", SHOT)
        browser.close()


if __name__ == "__main__":
    main()
