# -*- coding: utf-8 -*-
"""完整纯协议登录流程：登录 -> MFA 发码 -> （待验证码）校验。

device_id 使用数美 SDK 生成的 88 字符 base64（从浏览器 localStorage .thumbcache_* 取得）。
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
# 浏览器生成的数美 device_id（88 字符 base64）
DEVICE_ID = ("BNaTEWNfiFMdnqIEm6bgYReu82v3DlNH+eFGqTXHGyRxbMKwiK2W2QmI9jXc3qd"
             "DhyPjyUerU43GzO70hgtlu3g==")


def enc_post(sess: requests.Session, path: str, payload: dict) -> requests.Response:
    plain = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
    key_hdr, ct = encrypt_body(plain)
    h = base_headers(DEVICE_ID)
    h["x-request-encryption-key"] = key_hdr
    return sess.post(BASE + path, data=ct, headers=h, timeout=30)


def plain_post(sess: requests.Session, path: str, payload: dict) -> requests.Response:
    h = base_headers(DEVICE_ID)
    return sess.post(BASE + path, json=payload, headers=h, timeout=30)


def main() -> None:
    sess = requests.Session()
    sess.trust_env = False

    # 1) 登录
    login_body = {
        "email": EMAIL, "mobile": "", "area_code": "", "password": PASSWORD,
        "device_id": DEVICE_ID, "os": "web", "credential_id": "",
    }
    r = enc_post(sess, "/api/v0/users/login", login_body)
    print("== login ==", r.status_code)
    print(r.text[:400])
    data = r.json().get("data") or {}
    if data.get("biz_code") != 14:
        print("未进入 MFA，终止")
        return
    mfa_sid = data["biz_data"]["mfa_session_id"]
    print("mfa_session_id:", mfa_sid)

    # 2) MFA 发码 —— 先用最小字段探测 schema
    for label, body, use_enc in [
        ("min {mfa_session_id}", {"mfa_session_id": mfa_sid}, False),
        ("+shumei_device_id=''", {"mfa_session_id": mfa_sid, "shumei_device_id": ""}, False),
        ("enc min", {"mfa_session_id": mfa_sid}, True),
    ]:
        try:
            r2 = (enc_post if use_enc else plain_post)(
                sess, "/api/v0/users/mfa/create_verification_code", body)
            print(f"\n== mfa/create_verification_code [{label}] ==", r2.status_code)
            print(r2.text[:400])
        except Exception as exc:  # noqa: BLE001
            print(f"\n[{label}] error:", exc)


if __name__ == "__main__":
    main()
