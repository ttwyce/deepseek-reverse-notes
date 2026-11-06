# -*- coding: utf-8 -*-
"""决定性实验：让真实浏览器自己完成「密码登录」，观察是否仍 biz_code 11。

若浏览器同样 11 → 账号/IP 级风控，纯协议与浏览器都无解。
若浏览器成功 → 说明纯协议请求缺少浏览器才有的细节，可据此补齐。
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



import json
import sys
import time

from playwright.sync_api import sync_playwright

EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")
WORK = r"F:\dshh\deepseeka\work"


def main() -> None:
    api_log: list[str] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=[
            "--disable-blink-features=AutomationControlled", "--no-first-run"])
        ctx = browser.new_context(viewport={"width": 1366, "height": 900},
                                  locale="zh-CN", timezone_id="Asia/Shanghai")
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
        page = ctx.new_page()

        def on_response(resp):
            url = resp.url
            if "/api/v0/users/login" in url or "/create_guest_challenge" in url:
                try:
                    body = resp.text()[:400]
                except Exception:  # noqa: BLE001
                    body = "<no body>"
                api_log.append(f"{resp.status} {url} -> {body}")
                print("API", resp.status, url)
                print("    ", body)

        page.on("response", on_response)
        page.goto("https://chat.deepseek.com/sign_in",
                  wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)

        # 切到「密码登录」
        try:
            page.click("text=密码登录", timeout=8000)
            print("clicked 密码登录")
        except Exception as exc:  # noqa: BLE001
            print("click 密码登录 failed:", exc)
        page.wait_for_timeout(2500)
        print("== inputs after switch ==")
        for el in page.query_selector_all("input"):
            print("  input", el.get_attribute("type"),
                  el.get_attribute("placeholder"))

        # 填账号
        filled = False
        for sel in ["input[type=text]", "input[type=email]",
                    "input[placeholder*='邮箱']", "input[placeholder*='手机']"]:
            try:
                if page.locator(sel).count() > 0:
                    page.fill(sel, EMAIL, timeout=5000)
                    print("filled account via", sel)
                    filled = True
                    break
            except Exception:  # noqa: BLE001
                continue
        if not filled:
            inputs = page.query_selector_all("input")
            if inputs:
                inputs[0].fill(EMAIL)
                print("filled account via inputs[0]")

        # 填密码
        try:
            page.fill("input[type=password]", PASSWORD, timeout=5000)
            print("filled password")
        except Exception as exc:  # noqa: BLE001
            print("fill password failed:", exc)

        page.screenshot(path=WORK + r"\pw_pwd_form.png")

        # 提交
        for sel in ["button:has-text('登录')", "button[type=submit]"]:
            try:
                if page.locator(sel).count() > 0:
                    page.click(sel, timeout=5000)
                    print("clicked submit", sel)
                    break
            except Exception:  # noqa: BLE001
                continue

        print("waiting 60s for result ...")
        for _ in range(30):
            page.wait_for_timeout(2000)
            if "/sign_in" not in page.url:
                print("url changed ->", page.url)
                break

        page.wait_for_timeout(4000)
        page.screenshot(path=WORK + r"\pw_pwd_result.png")
        print("== body text ==")
        try:
            print(page.inner_text("body")[:800])
        except Exception:  # noqa: BLE001
            pass

        storage = page.evaluate("""() => {
            const o = {};
            for (let i=0;i<localStorage.length;i++){const k=localStorage.key(i);
              o[k]=localStorage.getItem(k);}
            return o;}""")
        print("== userToken ==", storage.get("userToken"))
        print("== userInfo ==", storage.get("__appKit_userInfo"))
        ctx.storage_state(path=WORK + r"\pw_pwd_state.json")
        browser.close()

    print("\n=== api log ===")
    for line in api_log:
        print(line)


if __name__ == "__main__":
    main()
