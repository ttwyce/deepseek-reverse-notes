# -*- coding: utf-8 -*-
"""发码接口人机验证字段矩阵：判断服务端究竟校验哪个 token。

每个变体独立取 PoW（PoW 一次性），经 127.0.0.1:7890。
复用项目 tools/deepseek_pow.py 的 solve / build_pow_header。
"""
from __future__ import annotations

import json
import sys
import time

import requests

sys.path.insert(0, "tools")
from deepseek_pow import build_pow_header, solve  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

PROXY = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
BASE = "https://chat.deepseek.com"
EMAIL = "demo.user+4@example.com"
DEV = ("BHG7wvoq0vl2CIM7ITh1A0dozq/HkyMrV5xKXXMBk0XDLHRxZ72mJLeXHD"
       "+A/yXigeVb2wzQjmKGx7sjqXFn/WQ==")


def headers_common() -> dict:
    return {
        "content-type": "application/json",
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "x-client-bundle-id": "com.deepseek.chat",
        "x-client-platform": "web",
        "x-client-version": "2.7.0",
        "x-client-locale": "en_US",
        "x-client-timezone-offset": "32400",
        "user-agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
        "origin": BASE,
        "referer": f"{BASE}/sign_up",
    }


def fresh_pow(s: requests.Session) -> str | None:
    r = s.post(f"{BASE}/api/v0/users/create_guest_challenge", headers=headers_common(),
               json={"target_path": "/api/v0/users/create_email_verification_code"},
               proxies=PROXY, timeout=30)
    j = r.json()
    gc = ((j.get("data") or {}).get("biz_data") or {}).get("guest_challenge") or {}
    if not gc.get("challenge"):
        print("   [PoW] 取挑战失败:", json.dumps(j, ensure_ascii=False)[:200])
        return None
    try:
        hdr, nonce = build_pow_header(gc)
        print(f"   [PoW] nonce={nonce}")
        return hdr
    except Exception as e:
        print("   [PoW] 求解失败:", e)
        return None


VARIANTS = [
    ("A 基线（仅 device_id）", {}),
    ("B turnstile_token 假值", {"turnstile_token": "FAKE_TOK_AAA"}),
    ("C hcaptcha_token 假值", {"hcaptcha_token": "P1_FAKE_HCAP"}),
    ("D 两者都假", {"turnstile_token": "FAKE_TOK_AAA", "hcaptcha_token": "P1_FAKE_HCAP"}),
    ("E turnstile_token 空串", {"turnstile_token": ""}),
    ("F shumei_verification 假", {"shumei_verification": {"rid": "fakerid123", "region": "jp"}}),
    ("H 三选全带", {"turnstile_token": "FAKE_TOK_AAA", "hcaptcha_token": "P1_FAKE_HCAP",
                 "shumei_verification": {"rid": "fakerid123", "region": "jp"}}),
]


def main() -> None:
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    for name, extra in VARIANTS:
        if only and only not in name:
            continue
        print(f"\n=== {name}")
        s = requests.Session()
        hdr = fresh_pow(s)
        if not hdr:
            continue
        payload = {"email": EMAIL, "locale": "en_US", "scenario": "register", "device_id": DEV}
        payload.update(extra)
        h = headers_common()
        h["x-ds-guest-pow-response"] = hdr
        try:
            r = s.post(f"{BASE}/api/v0/users/create_email_verification_code",
                       headers=h, json=payload, proxies=PROXY, timeout=30)
            try:
                j = r.json()
            except Exception:
                j = {"raw": r.text[:300]}
            print(f"  HTTP {r.status_code} -> {json.dumps(j, ensure_ascii=False)[:320]}")
        except Exception as e:
            print(f"  异常 {e}")
        time.sleep(1.5)


if __name__ == "__main__":
    main()
