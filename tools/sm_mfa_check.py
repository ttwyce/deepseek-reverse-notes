# -*- coding: utf-8 -*-
"""MFA 校验：用邮箱收到的验证码换取 auth_token。

用法：
    python tools/sm_mfa_check.py 123456
    python tools/sm_mfa_check.py            # 交互式输入
"""
from __future__ import annotations

import json
import sys

import requests

sys.path.insert(0, r"F:\dshh\deepseeka\tools")
from enc_login_test import base_headers  # noqa: E402
from proto_login_full import BASE, WORK  # noqa: E402

CHECK = "/api/v0/users/mfa/check_verification_code"


def main() -> None:
    with open(WORK + r"\mfa_state.json", encoding="utf-8") as f:
        st = json.load(f)
    code = sys.argv[1].strip() if len(sys.argv) > 1 else input("邮箱验证码: ").strip()
    sess = requests.Session()
    sess.trust_env = False
    r = sess.post(BASE + CHECK,
                  json={"mfa_session_id": st["mfa_session_id"],
                        "verification_code": code},
                  headers=base_headers(st["device_id"]), timeout=30)
    print("http:", r.status_code)
    print(r.text[:2000])
    ck = sess.cookies.get_dict()
    if ck:
        print("cookies:", list(ck))
    try:
        j = r.json()
        data = (j.get("data") or {})
        if data.get("biz_code") == 0:
            out = {"raw": j, "device_id": st["device_id"], "email": st.get("email")}
            with open(WORK + r"\auth_mfa_result.json", "w", encoding="utf-8") as f:
                json.dump(out, f, ensure_ascii=False, indent=2)
            print("saved ->", WORK + r"\auth_mfa_result.json")
    except Exception:
        pass


if __name__ == "__main__":
    main()
