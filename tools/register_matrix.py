# -*- coding: utf-8 -*-
"""register 閭浣撳瓧娈?澶寸粍鍚堢煩闃碉細瀹氫綅 REGISTER_FROM_MAINLAND(biz_code 6) 鐨勫垽瀹氳緭鍏ャ€?
姣忎釜鐢ㄤ緥鐙珛鐢宠 guest challenge + 姹傝В PoW锛圥oW 涓€娆℃€э紝澶嶇敤浼?40301锛夈€?鍏ㄩ儴缁忔棩鏈唬鐞嗗嚭鍙?43.206.230.77銆?
鐢ㄦ硶锛歱ython tools\\register_matrix.py
"""
from __future__ import annotations

import json
import sys
import time

import requests

sys.path.insert(0, r"F:\dshh\deepseeka\tools")
from deepseek_pow import API, HEADERS, build_pow_header  # noqa: E402

PROXY = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
REG = "/api/v0/users/register"
CODE = "/api/v0/users/create_email_verification_code"
EMAIL = "demo.user+4@example.com"
PASSWORD = __import__("os").environ.get("DS_REG_PASSWORD", "")  # 不落盘，见 DS_REG_PASSWORD
DEV = "B" + "a" * 87

S = requests.Session()
S.trust_env = False
S.proxies = PROXY


def pow_header(path: str) -> str:
    r = S.post(API + "/api/v0/users/create_guest_challenge",
               json={"target_path": path}, headers=HEADERS, timeout=30)
    gc = (r.json().get("data") or {}).get("biz_data", {}).get("guest_challenge")
    if not gc:
        raise SystemExit("challenge 澶辫触: " + r.text[:300])
    header, _nonce = build_pow_header(gc)
    return header


def run(path: str, body: dict, hdr_over: dict) -> None:
    h = dict(HEADERS)
    h.update(hdr_over)
    h["X-DS-Guest-Pow-Response"] = pow_header(path)
    r = S.post(API + path, json=body, headers=h, timeout=40)
    try:
        j = r.json()
    except Exception:
        print("  HTTP", r.status_code, r.text[:200])
        return
    d = j.get("data") or {}
    print(f"  HTTP {r.status_code} code={j.get('code')} biz_code={d.get('biz_code')} "
          f"msg={d.get('biz_msg') or j.get('msg')}")


def main() -> None:
    payload = {"email": EMAIL, "email_verification_code": "000000", "password": PASSWORD}

    cases = [
        ("A 鍩虹嚎 tz=28800 zh_CN region=JP", REG,
         {"payload": payload, "region": "JP", "locale": "zh_CN", "os": "android", "device_id": DEV},
         {}),
        ("B tz=32400 en_US region=JP", REG,
         {"payload": payload, "region": "JP", "locale": "en_US", "os": "android", "device_id": DEV},
         {"x-client-timezone-offset": "32400", "x-client-locale": "en_US",
          "Accept-Language": "en-US,en;q=0.9"}),
        ("C tz=0 en_US region=US", REG,
         {"payload": payload, "region": "US", "locale": "en_US", "os": "android", "device_id": DEV},
         {"x-client-timezone-offset": "0", "x-client-locale": "en_US",
          "Accept-Language": "en-US,en;q=0.9"}),
        ("D 鏃?region en_US web", REG,
         {"payload": payload, "region": "", "locale": "en_US", "os": "web", "device_id": DEV},
         {"x-client-timezone-offset": "-300", "x-client-locale": "en_US",
          "Accept-Language": "en-US,en;q=0.9"}),
        ("E 鏃?x-client-* 澶?region=JP", REG,
         {"payload": payload, "region": "JP", "locale": "en_US", "os": "android", "device_id": DEV},
         {"x-client-timezone-offset": "", "x-client-locale": "", "Accept-Language": "en-US"}),
    ]
    for tag, path, body, ov in cases:
        print(f"\n[{tag}]")
        try:
            run(path, body, ov)
        except SystemExit as e:
            print("  ", e)
        time.sleep(2)

    print("\n[F 鍙戠爜 en_US/tz=32400]")
    run(CODE, {"email": EMAIL, "locale": "en_US", "device_id": DEV,
               "scenario": "register", "turnstile_token": ""},
        {"x-client-timezone-offset": "32400", "x-client-locale": "en_US",
         "Accept-Language": "en-US,en;q=0.9"})


if __name__ == "__main__":
    main()
