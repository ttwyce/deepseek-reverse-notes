# -*- coding: utf-8 -*-
"""浏览器登录到 MFA 页面后点「发送验证码」，捕获全部 /api/ 请求。"""
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



import base64
import json

from playwright.sync_api import sync_playwright

EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")
WORK = r"F:\dshh\deepseeka\work"
CHROME = (r"F:\dshh\deepseeka\tools\pw-browsers\chromium-1248"
          r"\chrome-win64\chrome.exe")

caps: list[dict] = []


def main() -> None:
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, executable_path=CHROME,
                              args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(
            locale="zh-CN", timezone_id="Asia/Shanghai",
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/156.0.0.0 Safari/537.36"))
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = ctx.new_page()

        def on_resp(r):
            if "/api/v0/" not in r.url:
                return
            e = {"url": r.url, "status": r.status, "method": r.request.method}
            try:
                e["resp"] = r.text()[:500]
            except Exception:  # noqa: BLE001
                e["resp"] = "<bin>"
            try:
                raw = r.request.post_data_buffer
                if raw:
                    e["body_b64"] = base64.b64encode(raw).decode()
                    e["body_len"] = len(raw)
            except Exception:  # noqa: BLE001
                pass
            caps.append(e)
            print(f"[CAP] {r.request.method} {r.url} -> {r.status}")

        page.on("response", on_resp)
        page.goto("https://chat.deepseek.com/sign_in", wait_until="domcontentloaded")
        page.wait_for_timeout(6000)

        page.evaluate("""() => {
            for (const el of document.querySelectorAll('.ds-button__content')) {
                if (el.textContent.trim() === '密码登录') {
                    (el.closest('button') || el.parentElement).click(); return;
                }
            }
        }""")
        page.wait_for_timeout(1500)
        page.fill("input[placeholder*='手机号/邮箱']", EMAIL)
        page.fill("input[type=password]", PASSWORD)
        page.evaluate("""() => {
            for (const el of document.querySelectorAll('.ds-button__content')) {
                if (el.textContent.trim() === '登录') {
                    (el.closest('button') || el.parentElement).click(); return;
                }
            }
        }""")

        # 等 MFA 页面出现
        for _ in range(20):
            page.wait_for_timeout(1000)
            txt = page.inner_text("body")
            if "验证账号" in txt or "验证并登录" in txt or "发送验证码" in txt:
                print("[MFA page ready]")
                break
        print("body snippet:", page.inner_text("body")[:300].replace("\n", " | "))

        # 点发送验证码
        clicked = page.evaluate("""() => {
            for (const el of document.querySelectorAll('.ds-button__content')) {
                const t = el.textContent.trim();
                if (t === '发送验证码' || t === '获取验证码') {
                    (el.closest('button') || el.parentElement).click();
                    return t;
                }
            }
            return null;
        }""")
        print("clicked:", clicked)
        page.wait_for_timeout(10000)
        page.screenshot(path=WORK + r"\pw_mfa2.png", full_page=True)

        with open(WORK + r"\pw_mfa_capture2.json", "w", encoding="utf-8") as f:
            json.dump(caps, f, ensure_ascii=False, indent=2)
        print(f"\ntotal {len(caps)} api calls")
        for e in caps:
            print(f"  {e['method']} {e['url']} -> {e['status']}  body_len={e.get('body_len')}")
        b.close()


if __name__ == "__main__":
    main()
