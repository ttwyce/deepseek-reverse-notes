# -*- coding: utf-8 -*-
"""提交 MFA 邮箱验证码完成登录（纯协议，复用 sm_full_login.py 保存的 mfa_state.json）。

用法：
    set DS_EMAIL / DS_PASSWORD（或 local_config.py）
    python tools\\sm_submit_code.py <6位验证码>

流程：mfa/check_verification_code（明文 JSON）-> 拿到 user.token -> 落盘 work\\auth_token.json
"""
from __future__ import annotations

import json
import sys

import requests

sys.path.insert(0, r"F:\dshh\deepseeka\tools")
from enc_login_test import base_headers  # noqa: E402
from proto_login_full import BASE, EMAIL, WORK  # noqa: E402

TARGET = "/api/v0/users/mfa/check_verification_code"


def main() -> None:
    code = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    if not code:
        print("用法: python tools\\sm_submit_code.py <验证码>")
        return
    with open(WORK + r"\mfa_state.json", "r", encoding="utf-8") as f:
        st = json.load(f)
    device_id = st["device_id"]
    sid = st["mfa_session_id"]
    print("email:", st.get("email") or EMAIL)
    print("device_id len:", len(device_id), "mfa_session_id:", sid[:20], "...")

    sess = requests.Session()
    sess.trust_env = False
    h = base_headers(device_id)
    # MFA 两个接口只接受明文 JSON（加密返回 40007 REQUEST_DECRYPT_NOT_ALLOWED）
    r = sess.post(BASE + TARGET,
                  json={"mfa_session_id": sid, "verification_code": code},
                  headers=h, timeout=30)
    print("check:", r.status_code)
    txt = r.text
    print(txt[:600])
    try:
        j = r.json()
    except Exception:  # noqa: BLE001
        return
    data = j.get("data") or {}
    print("biz_code:", data.get("biz_code"), data.get("biz_msg"))
    user = ((data.get("biz_data") or {}).get("user") or {})
    token = user.get("token") or ""
    if token:
        out = {"token": token, "device_id": device_id, "email": st.get("email") or EMAIL,
               "user_id": user.get("id"), "mobile": user.get("mobile_number")}
        with open(WORK + r"\auth_token.json", "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print("TOKEN OK len=", len(token))
        print("token 前 12:", token[:12], "…", "后 6:", token[-6:])
        print("state ->", WORK + r"\auth_token.json")


if __name__ == "__main__":
    main()
