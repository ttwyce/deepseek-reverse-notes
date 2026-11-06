# -*- coding: utf-8 -*-
"""最终验证：device_id = "B" + 数美 deviceId（.thumbcache 值），纯协议登录。

同时打通 MFA 发码（需 GuestPow + deviceSnapshot 头）。
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

import requests

sys.path.insert(0, r"F:\dshh\deepseeka\tools")
from enc_login_test import base_headers, encrypt_body  # noqa: E402
from deepseek_pow import build_pow_header, get_guest_challenge  # noqa: E402

BASE = "https://chat.deepseek.com"
EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")
WORK = r"F:\dshh\deepseeka\work"
CHROME = (r"F:\dshh\deepseeka\tools\pw-browsers\chromium-1248"
          r"\chrome-win64\chrome.exe")


def grab_smid() -> str:
    """取数美 deviceId（.thumbcache 值，88 字符）。"""
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
        done = {"ok": False}

        def on_resp(r):
            if "deviceprofile" in r.url:
                done["ok"] = True

        page.on("response", on_resp)
        page.goto("https://chat.deepseek.com/", wait_until="domcontentloaded")
        t0 = time.time()
        while not done["ok"] and time.time() - t0 < 25:
            page.wait_for_timeout(400)
        page.wait_for_timeout(2500)
        st = page.evaluate("""() => {
            const o = {};
            for (let i = 0; i < localStorage.length; i++) {
                const k = localStorage.key(i); o[k] = localStorage.getItem(k);
            }
            return o;
        }""")
        b.close()
    for k, v in st.items():
        if k.startswith(".thumbcache_"):
            return v
    return ""


def enc_post(sess, path, payload, device_id, extra=None):
    plain = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
    key_hdr, ct = encrypt_body(plain)
    h = base_headers(device_id)
    if extra:
        h.update(extra)
    h["x-request-encryption-key"] = key_hdr
    return sess.post(BASE + path, data=ct, headers=h, timeout=30)


def main() -> None:
    smid = grab_smid()
    print("数美 deviceId:", smid, "len=", len(smid))
    if not smid:
        print("取不到，终止")
        return
    device_id = "B" + smid
    print("构造 device_id:", device_id, "len=", len(device_id))

    sess = requests.Session()
    sess.trust_env = False

    body = {"email": EMAIL, "mobile": "", "area_code": "", "password": PASSWORD,
            "device_id": device_id, "os": "web", "credential_id": ""}
    r = enc_post(sess, "/api/v0/users/login", body, device_id)
    print("\n== login ==", r.status_code, r.text[:300])
    data = r.json().get("data") or {}
    if data.get("biz_code") != 14:
        print("未进入 MFA")
        return
    sid = data["biz_data"]["mfa_session_id"]
    print("mfa_session_id:", sid)

    # MFA 发码需要 GuestPow
    target = "/api/v0/users/mfa/create_verification_code"
    try:
        gc = get_guest_challenge(target)
        pow_hdr, nonce = build_pow_header(gc)
        print("PoW nonce:", nonce)
    except Exception as exc:  # noqa: BLE001
        print("取 challenge 失败:", exc)
        return

    pl = {"mfa_session_id": sid, "shumei_device_id": ""}
    r2 = enc_post(sess, target, pl, device_id,
                  {"X-DS-Guest-Pow-Response": pow_hdr})
    print("\n== mfa/create_verification_code ==", r2.status_code)
    print(r2.text[:400])

    with open(WORK + r"\proto_login_state.json", "w", encoding="utf-8") as f:
        json.dump({"smid": smid, "device_id": device_id,
                   "mfa_session_id": sid}, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
