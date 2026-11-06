"""探明 os=web 分支的登录 schema（422 loc 细化判定）。"""
# --- credentials: 从环境变量或本地 local_config.py 读取（local_config 不入库）---
import os as _os


def _cred(key, default=""):
    v = _os.environ.get(key)
    if v:
        return v
    try:
        from local_config import CFG  # type: ignore
        return CFG.get(key, default)
    except Exception:
        return default


import json
import time
import uuid

from curl_cffi import requests as creq

EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")
DEV = "8f2a1b3c-4d5e-6f70-8192-a3b4c5d6e7f8"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
URL = "https://chat.deepseek.com/api/v0/users/login"


def post(body):
    h = {
        "User-Agent": UA,
        "Accept": "*/*",
        "Content-Type": "application/json",
        "Origin": "https://chat.deepseek.com",
        "Referer": "https://chat.deepseek.com/",
        "x-client-platform": "web",
        "x-client-version": "2.7.1",
        "x-client-bundle-id": "com.deepseek.chat",
        "x-client-locale": "zh_CN",
        "x-client-timezone-offset": "28800",
        "x-ds-trace-id": str(uuid.uuid4()),
    }
    s = creq.Session(impersonate="chrome")
    r = s.post(URL, data=json.dumps(body), headers=h, timeout=30)
    return r.status_code, r.text[:260]


def main():
    base = {"email": EMAIL, "password": PASSWORD, "os": "web"}
    cases = [
        ("web / 无 device_id", dict(base)),
        ("web / +device_id", {**base, "device_id": DEV}),
        ("web / +device_id+turnstile", {**base, "device_id": DEV, "turnstile_token": "x" * 20}),
        ("web / +device_id+hcaptcha", {**base, "device_id": DEV, "hcaptcha_token": "x" * 20}),
        ("web / +device_id+challenge", {**base, "device_id": DEV, "challenge": "x" * 20}),
        ("web / +device_id+credential_id", {**base, "device_id": DEV, "credential_id": "x" * 20}),
        ("web / +device_id+nonce+sig", {**base, "device_id": DEV, "nonce": "x", "signature": "y"}),
        ("web / +turnstile 无 device_id", {**base, "turnstile_token": "x" * 20}),
    ]
    for name, body in cases:
        try:
            code, txt = post(body)
        except Exception as e:  # noqa: BLE001
            code, txt = -1, f"EXC {e}"
        print(f"{name:34s} -> {code} {txt}")
        time.sleep(5)


if __name__ == "__main__":
    main()
