# -*- coding: utf-8 -*-
"""DeepSeek 纯协议登录完整链路：设备指纹 -> 登录 -> MFA 发码。

关键结论：
  device_id = "B" + 数美 deviceprofile 返回的 deviceId（88 字符 base64）
  该值由 Playwright 打开首页后从 localStorage 的 .thumbcache_* 读取。
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



import base64
import json
import sys
import time

import requests

sys.path.insert(0, r"F:\dshh\deepseeka\tools")
from enc_login_test import base_headers, encrypt_body  # noqa: E402
from deepseek_pow import solve  # noqa: E402

BASE = "https://chat.deepseek.com"
EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")
WORK = r"F:\dshh\deepseeka\work"
CHROME = (r"F:\dshh\deepseeka\tools\pw-browsers\chromium-1248"
          r"\chrome-win64\chrome.exe")


def grab_smid() -> str:
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
        page.on("response",
                lambda r: done.__setitem__("ok", True) if "deviceprofile" in r.url else None)
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


def get_challenge(sess, device_id, target_path) -> dict:
    h = base_headers(device_id)
    r = sess.post(BASE + "/api/v0/users/create_guest_challenge",
                  json={"target_path": target_path}, headers=h, timeout=30)
    j = r.json()
    gc = (j.get("data") or {}).get("biz_data") or {}
    gc = gc.get("guest_challenge") or gc
    return gc


def pow_header(gc: dict, target_path: str) -> str:
    challenge = gc["challenge"]
    salt = gc["salt"]
    expire_at = int(gc["expire_at"])
    difficulty = int(gc["difficulty"])
    nonce = solve(challenge, salt, expire_at, difficulty)
    sol = {
        "algorithm": gc.get("algorithm", "DeepSeekHashV1"),
        "challenge": challenge,
        "salt": salt,
        "signature": gc.get("signature", ""),
        "answer": nonce,
        "target_path": target_path,
    }
    raw = json.dumps(sol, separators=(",", ":"), ensure_ascii=False).encode()
    return base64.b64encode(raw).decode()


def main() -> None:
    smid = grab_smid()
    if not smid:
        print("取不到数美 deviceId")
        return
    device_id = "B" + smid
    print("device_id:", device_id[:50], "len=", len(device_id))

    sess = requests.Session()
    sess.trust_env = False

    body = {"email": EMAIL, "mobile": "", "area_code": "", "password": PASSWORD,
            "device_id": device_id, "os": "web", "credential_id": ""}
    r = enc_post(sess, "/api/v0/users/login", body, device_id)
    print("login:", r.status_code, r.text[:250])
    data = r.json().get("data") or {}
    if data.get("biz_code") != 14:
        return
    sid = data["biz_data"]["mfa_session_id"]

    target = "/api/v0/users/mfa/create_verification_code"
    gc = get_challenge(sess, device_id, target)
    print("challenge:", {k: gc.get(k) for k in ("algorithm", "difficulty", "expire_at")})
    hdr = pow_header(gc, target)
    print("pow header len:", len(hdr))

    for label, pl in [
        ("mfa_session_id only", {"mfa_session_id": sid}),
        ("+shumei_device_id=''", {"mfa_session_id": sid, "shumei_device_id": ""}),
    ]:
        rr = enc_post(sess, target, pl, device_id, {"X-DS-Guest-Pow-Response": hdr})
        print(f"\n[{label}] {rr.status_code}")
        print(" ", rr.text[:350])

    with open(WORK + r"\mfa_state.json", "w", encoding="utf-8") as f:
        json.dump({"device_id": device_id, "mfa_session_id": sid}, f,
                  ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
