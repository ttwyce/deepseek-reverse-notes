# -*- coding: utf-8 -*-
"""探测 create_email_verification_code 的邮箱域名白名单（scenario=register）。

对每个候选域名发一次验证码请求，据 biz_code 判断域名是否被支持：
  biz_code 4 = EMAIL_DOMAIN_NOT_SUPPORTED（不支持）
  其他（含 0 / 限流 / captcha）= 域名通过校验
每次请求前重新取 GuestPow 挑战。
"""
import json
import sys
import time

import requests

sys.path.insert(0, r"F:\dshh\deepseeka\tools")
from deepseek_pow import build_pow_header  # noqa: E402


def fetch_gc(session, hdrs, target_path):
    """取 guest challenge（带设备头，避免服务端走不同分支）。"""
    r = session.post(BASE + "/api/v0/users/create_guest_challenge",
                     headers=hdrs,
                     data=json.dumps({"target_path": target_path}).encode(),
                     timeout=30)
    payload = r.json()
    return payload["data"]["biz_data"]["guest_challenge"]

BASE = "https://chat.deepseek.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

DOMAINS = ["gmail.com", "outlook.com", "hotmail.com", "qq.com", "163.com",
           "126.com", "foxmail.com", "yahoo.com", "proton.me", "icloud.com",
           "example.org", "example.com"]


def headers(device_id):
    return {
        "User-Agent": UA,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Content-Type": "application/json",
        "Origin": BASE,
        "Referer": BASE + "/sign_in",
        "x-client-bundle-id": "com.deepseek.chat",
        "x-client-platform": "web",
        "x-client-version": "2.7.0",
        "x-client-locale": "zh_CN",
        "x-client-timezone-offset": "28800",
        "x-device-id": device_id,
        "x-device-model": "",
    }


def main():
    s = requests.Session()
    s.trust_env = False
    device_id = "8f3a1c2e-4b5d-4e6f-9a7b-1c2d3e4f5a6b"
    for dom in DOMAINS:
        email = "dsrev-probe-8f3a@" + dom
        try:
            gc = fetch_gc(s, headers(device_id),
                          "/api/v0/users/create_email_verification_code")
            pow_header, nonce = build_pow_header(gc)
        except Exception as exc:  # noqa: BLE001
            print(f"{dom:16s} POW-FAIL {type(exc).__name__}: {exc}")
            time.sleep(3)
            continue
        h = headers(device_id)
        h["X-DS-Guest-Pow-Response"] = pow_header
        body = {"email": email, "locale": "zh_CN", "device_id": device_id,
                "scenario": "register", "turnstile_token": ""}
        try:
            r = s.post(BASE + "/api/v0/users/create_email_verification_code",
                       headers=h, data=json.dumps(body).encode(), timeout=30)
            try:
                j = r.json()
                biz = (j.get("data") or {}).get("biz_code")
                msg = (j.get("data") or {}).get("biz_msg")
                if biz is None:
                    out = f"HTTP {r.status_code} code={j.get('code')} msg={j.get('msg')} detail={str(j.get('detail'))[:80]}"
                else:
                    verdict = "NOT_SUPPORTED" if biz == 4 else "SUPPORTED"
                    out = f"biz_code={biz} biz_msg={msg} -> {verdict}"
            except ValueError:
                out = f"HTTP {r.status_code} non-json {r.text[:120]}"
            print(f"{dom:16s} {out} (nonce={nonce})")
        except Exception as exc:  # noqa: BLE001
            print(f"{dom:16s} EXC {type(exc).__name__}: {exc}")
        time.sleep(3)


if __name__ == "__main__":
    main()
