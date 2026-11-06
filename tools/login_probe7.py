"""验证设备注册/会话预热是否能解除 RISK_DEVICE_DETECTED（直连，低频）。"""
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
import sys
import time

import requests

EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")
DEV = "8f2a1b3c-4d5e-6f70-8192-a3b4c5d6e7f8"
UA = "Dalvik/2.1.0 (Linux; U; Android 14; Pixel 6 Build/UQ1A.240205.004)"


def base_headers():
    return {
        "User-Agent": UA,
        "Accept": "*/*",
        "x-client-platform": "android",
        "x-client-version": "2.7.1",
        "x-client-bundle-id": "com.deepseek.chat",
        "x-client-locale": "zh_CN",
        "x-client-timezone-offset": "28800",
        "x-device-model": "Pixel 6",
    }


def login(sess, tag):
    h = base_headers()
    h["Content-Type"] = "application/json"
    body = {"email": EMAIL, "password": PASSWORD, "device_id": DEV, "os": "android"}
    r = sess.post(
        "https://chat.deepseek.com/api/v0/users/login",
        data=json.dumps(body),
        headers=h,
        timeout=30,
    )
    print(f"[{tag}] login {r.status_code} {r.text[:200]}")
    time.sleep(3)
    return r


def main():
    # S1: 先 GET 首页拿 cookie
    s1 = requests.Session()
    s1.headers.update({"User-Agent": UA})
    r = s1.get("https://chat.deepseek.com/", timeout=30)
    print(f"[S1] GET / -> {r.status_code}, cookies={list(s1.cookies.keys())}")
    login(s1, "S1")

    # S2: 先 auth_token/check_device
    s2 = requests.Session()
    s2.headers.update({"User-Agent": UA})
    h = base_headers()
    h["Content-Type"] = "application/json"
    r = s2.post(
        "https://chat.deepseek.com/api/v0/users/auth_token/check_device",
        data=json.dumps({"device_model": "Pixel 6", "device_id": DEV}),
        headers=h,
        timeout=30,
    )
    print(f"[S2] check_device {r.status_code} {r.text[:250]}")
    time.sleep(3)
    login(s2, "S2")

    # S3: 先 users/current
    s3 = requests.Session()
    s3.headers.update({"User-Agent": UA})
    r = s3.get("https://chat.deepseek.com/api/v0/users/current", headers=base_headers(), timeout=30)
    print(f"[S3] users/current {r.status_code} {r.text[:250]}")
    time.sleep(3)
    login(s3, "S3")
    return 0


if __name__ == "__main__":
    sys.exit(main())
