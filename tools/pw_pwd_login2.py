# -*- coding: utf-8 -*-
"""真实浏览器密码登录：切换 tab → 填邮箱密码 → 提交 → 捕获 login 响应。"""
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

from playwright.sync_api import sync_playwright

EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")
WORK = r"F:\dshh\deepseeka\work"


def main() -> None:
    logs: list[str] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=[
            "--disable-blink-features=AutomationControlled", "--no-first-run"])
        ctx = browser.new_context(viewport={"width": 1366, "height": 900},
                                  locale="zh-CN", timezone_id="Asia/Shanghai")
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
        page = ctx.new_page()

        def on_response(resp):
            if "/api/v0/" in resp.url and ("login" in resp.url or "challenge" in resp.url):
                try:
                    body = resp.text()[:500]
                except Exception:  # noqa: BLE001
                    body = "<no body>"
                logs.append(f"{resp.status} {resp.url}\n    {body}")
                print("API", resp.status, resp.url)
                print("    ", body)

        page.on("response", on_response)
        page.goto("https://chat.deepseek.com/sign_in",
                  wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)

        # 切到密码登录
        page.evaluate("""() => {
            for (const el of document.querySelectorAll('.ds-button__content')) {
                if ((el.textContent||'').trim() === '密码登录') {
                    (el.closest('button') || el.parentElement).click(); return;
                }
            }
        }""")
        page.wait_for_timeout(2500)

        page.fill("input[placeholder*='手机号/邮箱']", EMAIL, timeout=10000)
        page.fill("input[type=password]", PASSWORD, timeout=10000)
        print("filled form")

        # 点登录
        clicked = page.evaluate("""() => {
            for (const el of document.querySelectorAll('.ds-button__content')) {
                if ((el.textContent||'').trim() === '登录') {
                    (el.closest('button') || el.parentElement).click(); return true;
                }
            }
            return false;
        }""")
        print("submit clicked:", clicked)

        print("waiting 45s ...")
        for i in range(23):
            page.wait_for_timeout(2000)
            if "/sign_in" not in page.url:
                print("url changed ->", page.url)
                break

        page.wait_for_timeout(3000)
        page.screenshot(path=WORK + r"\pw_pwd_result.png")
        print("== body text ==")
        try:
            print(page.inner_text("body")[:600])
        except Exception:  # noqa: BLE001
            pass

        st = page.evaluate("""() => {
            const o = {};
            for (let i=0;i<localStorage.length;i++){const k=localStorage.key(i);
              o[k]=localStorage.getItem(k);}
            return o;}""")
        print("== userToken ==", st.get("userToken"))
        print("== userInfo ==", st.get("__appKit_userInfo"))
        json.dump(st, open(WORK + r"\pw_storage.json", "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        ctx.storage_state(path=WORK + r"\pw_pwd_state.json")
        browser.close()

    print("\n=== api log ===")
    for line in logs:
        print(line)


if __name__ == "__main__":
    main()
