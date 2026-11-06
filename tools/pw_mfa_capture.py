# -*- coding: utf-8 -*-
"""浏览器走完整登录 -> MFA，捕获 MFA 发码请求结构 + 新 device_id。

目的：拿到 mfa/create_verification_code 的请求/响应 schema，
以及每次会话新的数美 device_id，供纯协议复用。
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

from playwright.sync_api import sync_playwright

EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")
WORK = r"F:\dshh\deepseeka\work"
CHROME = (r"F:\dshh\deepseeka\tools\pw-browsers\chromium-1248"
          r"\chrome-win64\chrome.exe")

captured: list[dict] = []


def on_response(resp) -> None:
    url = resp.url
    if "/api/v0/users/" not in url:
        return
    if not any(k in url for k in ("login", "mfa", "verification", "challenge")):
        return
    try:
        body = resp.text()
    except Exception:  # noqa: BLE001
        body = "<binary>"
    req = resp.request
    entry = {
        "url": url,
        "status": resp.status,
        "method": req.method,
        "req_headers": dict(req.headers),
        "resp": body[:800],
    }
    try:
        raw = req.post_data_buffer
        if raw:
            entry["req_body_b64"] = __import__("base64").b64encode(raw).decode()
            entry["req_body_len"] = len(raw)
    except Exception:  # noqa: BLE001
        pass
    captured.append(entry)
    print(f"[CAP] {req.method} {url} -> {resp.status}")


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path=CHROME,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/156.0.0.0 Safari/537.36"),
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = ctx.new_page()
        page.on("response", on_response)

        page.goto("https://chat.deepseek.com/sign_in", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        # 切到密码登录
        page.evaluate("""() => {
            for (const el of document.querySelectorAll('.ds-button__content')) {
                if (el.textContent.trim() === '密码登录') {
                    (el.closest('button') || el.parentElement).click();
                    return true;
                }
            }
            return false;
        }""")
        page.wait_for_timeout(1500)

        # 填表
        page.fill("input[placeholder*='手机号/邮箱']", EMAIL)
        page.fill("input[type=password]", PASSWORD)
        page.wait_for_timeout(300)

        # 点登录
        page.evaluate("""() => {
            for (const el of document.querySelectorAll('.ds-button__content')) {
                if (el.textContent.trim() === '登录') {
                    (el.closest('button') || el.parentElement).click();
                    return true;
                }
            }
            return false;
        }""")
        page.wait_for_timeout(6000)
        print("URL after login:", page.url)

        # 设备标识快照
        storage = page.evaluate("""() => {
            const out = {};
            for (let i = 0; i < localStorage.length; i++) {
                const k = localStorage.key(i);
                out[k] = localStorage.getItem(k);
            }
            return out;
        }""")
        with open(WORK + r"\pw_mfa_storage.json", "w", encoding="utf-8") as f:
            json.dump(storage, f, ensure_ascii=False, indent=2)
        for k, v in storage.items():
            if "thumbcache" in k or "device" in k or "smid" in k.lower():
                print(f"  {k} = {v[:120]}")

        # 点「发送验证码」
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
        print("send-code button:", clicked)
        page.wait_for_timeout(8000)
        page.screenshot(path=WORK + r"\pw_mfa_page.png", full_page=True)

        with open(WORK + r"\pw_mfa_capture.json", "w", encoding="utf-8") as f:
            json.dump(captured, f, ensure_ascii=False, indent=2)
        print(f"\ncaptured {len(captured)} requests -> work\\pw_mfa_capture.json")

        ctx.storage_state(path=WORK + r"\pw_mfa_state.json")
        browser.close()


if __name__ == "__main__":
    sys.exit(main())
