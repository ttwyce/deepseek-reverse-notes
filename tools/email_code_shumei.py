# -*- coding: utf-8 -*-
"""注册发码：用数美真 rid 过 captcha（日本 IP）。

链路：数美 deviceprofile 换 88 字符 deviceId -> shumei_solver 自动点选拿 rid
      -> POST /api/v0/users/create_email_verification_code（明文 JSON）

用法：python tools\\email_code_shumei.py [--region CN] [--dev Bxxx] [--no-solve]
"""
from __future__ import annotations

import json
import sys
import time

import requests

sys.path.insert(0, r"F:\dshh\deepseeka\tools")
from proto_login_full import BASE  # noqa: E402
from enc_login_test import base_headers  # noqa: E402
from shumei_solver import solve  # noqa: E402
import sm_fp_client  # noqa: E402

PROXY = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
SM_URL = "https://fp-it-acc.portal101.cn/deviceprofile/v4"
TARGET = "/api/v0/users/create_email_verification_code"
EMAIL = "demo.user+4@example.com"

REGION = "CN"
DEV = ""
NO_SOLVE = "--no-solve" in sys.argv
for i, a in enumerate(sys.argv):
    if a == "--region" and i + 1 < len(sys.argv):
        REGION = sys.argv[i + 1]
    if a == "--dev" and i + 1 < len(sys.argv):
        DEV = sys.argv[i + 1]


def shumei_device_id() -> str:
    _uid, _pri, body = sm_fp_client.build_request(
        sm_fp_client.build_fields(sm_fp_client.load_template()))
    r = requests.post(SM_URL, json=body, headers=sm_fp_client.HEADERS,
                      proxies=PROXY, timeout=20)
    j = r.json()
    dev = ((j.get("detail") or {}).get("deviceId") or "")
    print(f"[shumei] HTTP {r.status_code} code={j.get('code')} "
          f"requestId={j.get('requestId')} deviceId_len={len(dev)}")
    if j.get("code") != 1100 or len(dev) != 88:
        raise SystemExit("数美换号失败: " + json.dumps(j, ensure_ascii=False)[:300])
    return dev


def send(dev: str, smid: str, rid: str) -> None:
    sess = requests.Session()
    sess.trust_env = False
    sess.proxies = PROXY
    payload = {
        "email": EMAIL,
        "locale": "en_US",
        "device_id": dev,
        "scenario": "register",
        "shumei_verification": {"region": REGION, "rid": rid},
        "shumei_device_id": smid,
        "hcaptcha_token": "",
        "turnstile_token": "",
    }
    t0 = time.time()
    r = sess.post(BASE + TARGET, json=payload, headers=base_headers(dev), timeout=40)
    print(f"\n[send] HTTP {r.status_code} ({time.time()-t0:.1f}s)")
    print("      ", r.text[:500])


def main() -> None:
    smid = DEV[1:] if DEV.startswith("B") else (DEV or shumei_device_id())
    dev = ("B" + smid) if not DEV.startswith("B") else DEV
    print("device_id :", dev[:18], "len", len(dev))

    rid = ""
    if not NO_SOLVE:
        t0 = time.time()
        res = solve(batch=4, rounds=3, verbose=True)
        print(f"[solve] ok={res.get('ok')} attempts={res.get('attempts')} "
              f"elapsed={time.time()-t0:.1f}s")
        if not res.get("ok"):
            print("求解失败，改用空 rid 只测接口反应")
        rid = res.get("rid") or ""
    print("rid       :", (rid[:24] + "...") if rid else "(空)")

    send(dev, smid, rid)


if __name__ == "__main__":
    main()
