# -*- coding: utf-8 -*-
"""纯协议登录 + MFA 发码探测。

device_id 由 Playwright 打开首页后从 localStorage 的 .thumbcache_* 读取
（数美 SDK 生成的 88 字符 base64 设备指纹），之后全流程走纯 requests。
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

import requests

sys.path.insert(0, r"F:\dshh\deepseeka\tools")
from enc_login_test import base_headers, encrypt_body  # noqa: E402

BASE = "https://chat.deepseek.com"
EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")
WORK = r"F:\dshh\deepseeka\work"
CHROME = (r"F:\dshh\deepseeka\tools\pw-browsers\chromium-1248"
          r"\chrome-win64\chrome.exe")


def grab_device_id() -> tuple[str, str]:
    """开浏览器首页，取 .thumbcache_* (数美 device_id) 与 deepseek-device-id。"""
    from playwright.sync_api import sync_playwright

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
        page.goto("https://chat.deepseek.com/", wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
        st = page.evaluate("""() => {
            const o = {};
            for (let i = 0; i < localStorage.length; i++) {
                const k = localStorage.key(i); o[k] = localStorage.getItem(k);
            }
            return o;
        }""")
        b.close()
    thumb = ""
    uuid = ""
    for k, v in st.items():
        if k.startswith(".thumbcache_"):
            thumb = v
        if k == "deepseek-device-id:chat":
            uuid = v
    return thumb, uuid


def enc_post(sess, path, payload, device_id, extra_headers=None):
    plain = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
    key_hdr, ct = encrypt_body(plain)
    h = base_headers(device_id)
    if extra_headers:
        h.update(extra_headers)
    h["x-request-encryption-key"] = key_hdr
    return sess.post(BASE + path, data=ct, headers=h, timeout=30)


def plain_post(sess, path, payload, device_id):
    h = base_headers(device_id)
    return sess.post(BASE + path, json=payload, headers=h, timeout=30)


def main() -> None:
    dev, uuid = grab_device_id()
    print("device_id(thumbcache):", dev[:40], "len=", len(dev))
    print("deepseek-device-id  :", uuid)
    if not dev:
        print("未取到数美 device_id，终止")
        return

    sess = requests.Session()
    sess.trust_env = False

    # 1) 纯协议登录
    body = {"email": EMAIL, "mobile": "", "area_code": "", "password": PASSWORD,
            "device_id": dev, "os": "web", "credential_id": ""}
    r = enc_post(sess, "/api/v0/users/login", body, dev)
    print("\n== login ==", r.status_code, r.text[:300])
    data = r.json().get("data") or {}
    if data.get("biz_code") != 14:
        print("未进入 MFA，终止")
        return
    sid = data["biz_data"]["mfa_session_id"]
    print("mfa_session_id:", sid)

    # 2) 探测 MFA 发码 schema
    trials = [
        ("min", {"mfa_session_id": sid}, False),
        ("+shumei_device_id=''", {"mfa_session_id": sid, "shumei_device_id": ""}, False),
        ("enc min", {"mfa_session_id": sid}, True),
        ("enc +shumei_device_id=''", {"mfa_session_id": sid, "shumei_device_id": ""}, True),
    ]
    for label, pl, use_enc in trials:
        try:
            rr = (enc_post(sess, "/api/v0/users/mfa/create_verification_code", pl, dev)
                  if use_enc else
                  plain_post(sess, "/api/v0/users/mfa/create_verification_code", pl, dev))
            print(f"\n== mfa/create_verification_code [{label}] ==", rr.status_code)
            print(rr.text[:400])
        except Exception as exc:  # noqa: BLE001
            print(f"\n[{label}] error:", exc)


if __name__ == "__main__":
    main()
