# -*- coding: utf-8 -*-
"""诊断：用 check_email_code 判断验证码是否有效（区分「码错」与「注册流程错」）。

用法: python tools\\check_code.py 979245
"""
from __future__ import annotations

import json
import sys

import requests

sys.path.insert(0, r"F:\dshh\deepseeka\tools")
from deepseek_pow import API, HEADERS, build_pow_header
from enc_login_test import base_headers

PROXY = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
PATH = "/api/v0/users/check_email_code"
STATE = r"F:\dshh\deepseeka\work\reg_state.json"


def main() -> None:
    code = sys.argv[1].strip()
    st = json.load(open(STATE, encoding="utf-8"))
    dev = st["device_id"]

    s = requests.Session()
    s.trust_env = False
    s.proxies = PROXY

    r = s.post(API + "/api/v0/users/create_guest_challenge",
               json={"target_path": PATH}, headers=HEADERS, timeout=30)
    jc = r.json()
    data = jc.get("data") or {}
    gc = (data.get("biz_data") or {}).get("guest_challenge")
    print("[challenge]", "ok" if gc else r.text[:300])
    print("[challenge-raw]", json.dumps(jc, ensure_ascii=False)[:400])

    h = dict(HEADERS)
    h.update(base_headers(dev))
    if gc:
        h["X-DS-Guest-Pow-Response"] = build_pow_header(gc)[0]
    else:
        print("[challenge] 未拿到挑战，跳过 PoW 头直接试")

    body = {"email": st["email"], "email_verification_code": code}
    r = s.post(API + PATH, json=body, headers=h, timeout=30)
    print("[check] HTTP", r.status_code)
    print(r.text[:600])
    try:
        d = r.json().get("data") or {}
        print(f"\nbiz_code={d.get('biz_code')} biz_msg={d.get('biz_msg')}")
        print("→", "验证码有效（问题在 register 流程）" if d.get("biz_code") == 0
              else "验证码无效/过期（问题在码本身）")
    except Exception as e:
        print("parse err", e)


if __name__ == "__main__":
    main()
