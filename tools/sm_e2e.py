# -*- coding: utf-8 -*-
"""端到端验证：数美求解器 -> rid -> DeepSeek create_sms_verification_code。

判定标准：
  若后端返回「人机验证失败 / RECAPTCHA_VERIFY_FAILED」=> rid 未被接受
  若返回其它业务码（手机号不存在 / 发送成功 / 需要 PoW）=> rid 已被接受
"""
from __future__ import annotations

import json
import sys
import uuid

import requests

sys.path.insert(0, r"F:\dshh\deepseeka\tools")
from proto_login_full import enc_post, get_challenge, pow_header  # noqa: E402
from shumei_solver import solve  # noqa: E402

TARGET = "/api/v0/users/create_sms_verification_code"
MOBILE = "13800138000"


def body_for(rid: str, device_id: str) -> dict:
    return {
        "locale": "zh_CN",
        "turnstile_token": "",
        "shumei_verification": {"region": "CN", "rid": rid},
        "hcaptcha_token": "",
        "device_id": device_id,
        "scenario": "login",
        "mobile_number": MOBILE,
    }


def run(label: str, with_pow: bool) -> None:
    print(f"\n===== {label} (pow={with_pow}) =====")
    r = solve(batch=4, rounds=3, verbose=False)
    print("solve:", {k: r.get(k) for k in ("ok", "attempts", "elapsed", "order")})
    if not r.get("ok"):
        return
    rid = r["rid"]
    dev = str(uuid.uuid4())
    sess = requests.Session()
    sess.trust_env = False
    body = body_for(rid, dev)
    extra = None
    if with_pow:
        gc = get_challenge(sess, dev, TARGET)
        print("challenge:", {k: gc.get(k) for k in ("algorithm", "difficulty")})
        extra = {"X-DS-Guest-Pow-Response": pow_header(gc, TARGET)}
    resp = enc_post(sess, TARGET, body, dev, extra)
    print("http:", resp.status_code)
    try:
        j = resp.json()
        print(json.dumps(j, ensure_ascii=False)[:800])
    except Exception:
        print(resp.text[:800])


def main() -> None:
    run("A 无 PoW", with_pow=False)
    run("B 带 PoW", with_pow=True)


if __name__ == "__main__":
    main()
