# -*- coding: utf-8 -*-
"""抓取浏览器登录请求的原始 body 字节（可能是密文）+ 加密头。"""
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


def main() -> None:
    captured: list[dict] = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=[
            "--disable-blink-features=AutomationControlled", "--no-first-run"])
        ctx = browser.new_context(viewport={"width": 1366, "height": 900},
                                  locale="zh-CN", timezone_id="Asia/Shanghai")
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
        page = ctx.new_page()

        def on_request(req):
            if "/api/v0/users/login" not in req.url:
                return
            buf = req.post_data_buffer
            info = {
                "url": req.url,
                "method": req.method,
                "headers": dict(req.headers),
                "body_len": len(buf) if buf else 0,
                "body_b64": base64.b64encode(buf).decode() if buf else None,
                "body_hex_head": buf[:64].hex() if buf else None,
            }
            captured.append(info)
            print("REQ", req.method, req.url)
            print("  headers:")
            for k, v in req.headers.items():
                print(f"    {k}: {v[:120]}")
            print("  body_len:", info["body_len"])
            print("  body_hex_head:", info["body_hex_head"])

        def on_response(resp):
            if "/api/v0/users/login" in resp.url:
                try:
                    print("RESP", resp.status, resp.text()[:400])
                except Exception:  # noqa: BLE001
                    pass

        page.on("request", on_request)
        page.on("response", on_response)
        page.goto("https://chat.deepseek.com/sign_in",
                  wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)

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
        page.evaluate("""() => {
            for (const el of document.querySelectorAll('.ds-button__content')) {
                if ((el.textContent||'').trim() === '登录') {
                    (el.closest('button') || el.parentElement).click(); return true;
                }
            }
            return false;
        }""")
        page.wait_for_timeout(15000)
        ctx.storage_state(path=WORK + r"\pw_req_state.json")
        browser.close()

    with open(WORK + r"\pw_login_request.json", "w", encoding="utf-8") as fh:
        json.dump(captured, fh, ensure_ascii=False, indent=2)
    print("\nsaved count=", len(captured))


if __name__ == "__main__":
    main()
