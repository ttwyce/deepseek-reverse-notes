# -*- coding: utf-8 -*-
"""对「同一个 mfa_session_id」重新发一封验证码（session 不变，只有邮件/码是新的）。

用途：邮件到达有延迟时，反复刷新同一个 session 的码，避免换 session 把旧码作废。

用法：python tools\\sm_resend_code.py
"""
from __future__ import annotations

import json
import os
import sys
import time

import requests

sys.path.insert(0, r"F:\dshh\deepseeka\tools")
from proto_login_full import BASE  # noqa: E402
from shumei_solver import solve  # noqa: E402
from enc_login_test import base_headers  # noqa: E402

STATE = r"F:\dshh\deepseeka\work\mfa_state.json"
TARGET = "/api/v0/users/mfa/create_verification_code"


def main() -> None:
    with open(STATE, encoding="utf-8") as f:
        st = json.load(f)
    sid = st["mfa_session_id"]
    dev = st["device_id"]
    smid = dev[1:] if dev.startswith("B") else dev
    print("session :", sid)
    print("device  :", dev[:18], "len", len(dev))

    res = solve(batch=4, rounds=3, verbose=True)
    print(f"solve   : ok={res.get('ok')} attempts={res.get('attempts')}")
    if not res.get("ok"):
        return

    payload = {
        "mfa_session_id": sid,
        "shumei_verification": {"region": "CN", "rid": res["rid"]},
        "hcaptcha_token": "",
        "shumei_device_id": smid,
        "turnstile_token": "",
    }
    sess = requests.Session()
    sess.trust_env = False
    r = sess.post(BASE + TARGET, json=payload, headers=base_headers(dev), timeout=30)
    print("send    :", r.status_code, r.text[:300])

    st["rid"] = res["rid"]
    st["sent_at"] = time.strftime("%H:%M:%S")
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)
    print(f"\n>>> 同一 session 重发完成 {st['sent_at']}（session 未变）")


if __name__ == "__main__":
    main()
