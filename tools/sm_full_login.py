# -*- coding: utf-8 -*-
"""DeepSeek 完整登录链路：账号密码 -> 邮箱 MFA 发码（数美全自动）。

步骤：
  1. login（email + password）-> biz_code 14 + mfa_session_id
  2. shumei_solver.solve() -> rid
  3. mfa/create_verification_code（shumei_verification + shumei_device_id + PoW）-> 邮件发出
"""
from __future__ import annotations

import json
import sys

import requests

sys.path.insert(0, r"F:\dshh\deepseeka\tools")
from proto_login_full import (  # noqa: E402
    EMAIL, PASSWORD, WORK, enc_post, get_challenge, grab_smid, pow_header,
)
from shumei_solver import solve  # noqa: E402

TARGET = "/api/v0/users/mfa/create_verification_code"


def main() -> None:
    smid = grab_smid()
    print("smid len:", len(smid))
    if not smid:
        print("取不到数美 deviceId")
        return
    device_id = "B" + smid
    sess = requests.Session()
    sess.trust_env = False

    # 1. 登录
    body = {"email": EMAIL, "mobile": "", "area_code": "", "password": PASSWORD,
            "device_id": device_id, "os": "web", "credential_id": ""}
    r = enc_post(sess, "/api/v0/users/login", body, device_id)
    print("login:", r.status_code, r.text[:300])
    data = (r.json().get("data") or {})
    if data.get("biz_code") != 14:
        print("非 MFA 分支 biz_code =", data.get("biz_code"), data.get("biz_msg"))
        return
    sid = data["biz_data"]["mfa_session_id"]
    print("mfa_session_id:", sid[:24], "...")

    # 2. 解数美
    res = solve(batch=4, rounds=3, verbose=True)
    print("solve:", {k: res.get(k) for k in ("ok", "attempts", "elapsed", "order")})
    if not res.get("ok"):
        print("求解失败")
        return

    # 3. MFA 发码（该接口只接受明文 JSON，加密会返回 40007 REQUEST_DECRYPT_NOT_ALLOWED）
    payload = {
        "mfa_session_id": sid,
        "shumei_verification": {"region": "CN", "rid": res["rid"]},
        "hcaptcha_token": "",
        "shumei_device_id": smid,
        "turnstile_token": "",
    }
    from enc_login_test import base_headers  # noqa: E402
    from proto_login_full import BASE  # noqa: E402
    rp = sess.post(BASE + TARGET, json=payload, headers=base_headers(device_id), timeout=30)
    print("mfa send (plain):", rp.status_code, rp.text[:400])
    with open(WORK + r"\mfa_state.json", "w", encoding="utf-8") as f:
        json.dump({"device_id": device_id, "mfa_session_id": sid,
                   "rid": res["rid"], "email": EMAIL}, f, ensure_ascii=False, indent=2)
    print("state ->", WORK + r"\mfa_state.json")


if __name__ == "__main__":
    main()
