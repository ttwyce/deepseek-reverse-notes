# -*- coding: utf-8 -*-
"""邮箱注册链路探测（走日本代理出口）。

结论目标：
  1) create_email_verification_code 在非国内 IP 下是否仍强制 Cloudflare Turnstile
  2) /api/v0/users/register 邮箱体是否还返回 biz_code 6 REGISTER_FROM_MAINLAND
  3) scenario 字段的合法取值

用法：
    python tools\\email_reg_probe.py code      # 只测发码
    python tools\\email_reg_probe.py reg       # 只测 register
    python tools\\email_reg_probe.py all
"""
from __future__ import annotations

import json
import os
import sys
import time

import requests

sys.path.insert(0, r"F:\dshh\deepseeka\tools")
from deepseek_pow import API, HEADERS, build_pow_header  # noqa: E402

PROXY = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
CODE_PATH = "/api/v0/users/create_email_verification_code"
REG_PATH = "/api/v0/users/register"

EMAIL = os.environ.get("DS_EMAIL") or "demo.user+4@example.com"
PASSWORD = os.environ.get("DS_PASSWORD") or ""
DEVICE_ID = os.environ.get("DS_DEVICE_ID") or ""


def _cred(key: str, default: str = "") -> str:
    try:
        from local_config import CFG  # type: ignore
        return CFG.get(key, default)
    except Exception:
        return default


PASSWORD = PASSWORD or _cred("DS_PASSWORD")
DEVICE_ID = DEVICE_ID or _cred("DS_DEVICE_ID")

S = requests.Session()
S.trust_env = False
S.proxies = PROXY


def post(path: str, body: dict, extra: dict | None = None) -> requests.Response:
    h = dict(HEADERS)
    if extra:
        h.update(extra)
    return S.post(API + path, json=body, headers=h, timeout=40)


def pow_for(path: str) -> str:
    r = post("/api/v0/users/create_guest_challenge", {"target_path": path})
    j = r.json()
    gc = (j.get("data") or {}).get("biz_data", {}).get("guest_challenge")
    if not gc:
        raise SystemExit(f"guest_challenge 失败: {json.dumps(j, ensure_ascii=False)[:400]}")
    header, nonce = build_pow_header(gc)
    print(f"  PoW nonce={nonce} target={gc.get('target_path')}")
    return header


def show(tag: str, r: requests.Response) -> dict:
    try:
        j = r.json()
    except Exception:
        print(f"{tag:34s} HTTP {r.status_code}  {r.text[:220]}")
        return {}
    d = j.get("data") or {}
    biz = d.get("biz_code", j.get("code"))
    msg = d.get("biz_msg") or j.get("msg") or ""
    print(f"{tag:34s} HTTP {r.status_code}  code={j.get('code')} biz_code={biz} msg={msg}")
    if biz not in (0, None):
        extra = json.dumps(d.get("biz_data") or {}, ensure_ascii=False)
        print(f"{'':34s}   biz_data={extra[:260]}")
    return j


def probe_code() -> None:
    print("\n=== [1] create_email_verification_code（日本出口）===")
    header = pow_for(CODE_PATH)
    dev = DEVICE_ID or ("B" + "a" * 87)

    cases = [
        ("no-scenario no-turnstile", {"email": EMAIL, "locale": "zh_CN", "device_id": dev}),
        ("scenario=register", {"email": EMAIL, "locale": "zh_CN", "device_id": dev,
                               "scenario": "register", "turnstile_token": ""}),
        ("scenario=register+shumei", {"email": EMAIL, "locale": "zh_CN", "device_id": dev,
                                      "scenario": "register", "turnstile_token": "",
                                      "shumei_verification": {"region": "JP", "rid": ""}}),
    ]
    for tag, body in cases:
        r = post(CODE_PATH, body, {"X-DS-Guest-Pow-Response": header})
        show(tag, r)
        time.sleep(2)


def probe_register() -> None:
    print("\n=== [2] register 邮箱体（日本出口）===")
    header = pow_for(REG_PATH)
    dev = DEVICE_ID or ("B" + "a" * 87)
    payload = {"email": EMAIL, "email_verification_code": "000000",
               "password": PASSWORD or "Xx123456!"}
    cases = [
        ("os=android region=JP", {"region": "JP", "locale": "zh_CN", "os": "android",
                                  "device_id": dev, "payload": payload}),
        ("os=android region=CN", {"region": "CN", "locale": "zh_CN", "os": "android",
                                  "device_id": dev, "payload": payload}),
        ("os=web region=JP", {"region": "JP", "locale": "zh_CN", "os": "web",
                              "device_id": dev, "payload": payload}),
    ]
    for tag, body in cases:
        r = post(REG_PATH, body, {"X-DS-Guest-Pow-Response": header})
        show(tag, r)
        time.sleep(2)


def main() -> None:
    mode = (sys.argv[1] if len(sys.argv) > 1 else "all").lower()
    print("email     :", EMAIL)
    print("device_id :", (DEVICE_ID or "<B+a*87>")[:20], "len", len(DEVICE_ID))
    r = S.get("https://api.ipify.org?format=json", timeout=20)
    print("出口 IP   :", r.text)
    if mode in ("code", "all"):
        probe_code()
    if mode in ("reg", "all"):
        probe_register()


if __name__ == "__main__":
    main()
