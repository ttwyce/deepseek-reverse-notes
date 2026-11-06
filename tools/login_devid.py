"""判定 biz_code 11 是否与 device_id 内容有关。

思路：同一账号、同一 IP、同一 UA，只改 device_id 的形态。
若所有形态都返回 biz_code 11 => 服务端不看 device_id 内容，11 来自其他信号。
若某些形态返回别的 biz_code / 422 => device_id 内容参与风控判定。
"""
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
import os
import time

import requests

BASE = "https://chat.deepseek.com"
EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

HEADERS = {
    "User-Agent": UA,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Content-Type": "application/json",
    "Origin": BASE,
    "Referer": BASE + "/",
    "x-client-platform": "android",
    "x-client-version": "2.7.1",
    "x-client-bundle-id": "com.deepseek.chat",
    "x-client-locale": "zh_CN",
    "x-client-timezone-offset": "28800",
    "x-device-model": "Pixel 6",
}

CASES = [
    ("32x-a", "a" * 32),
    ("empty", ""),
    ("1char", "x"),
    ("smid-like-32", "2026102510ab12cd34ef56789012abcd"),
    ("hex64", "0123456789abcdef" * 4),
]


def post_login(device_id):
    body = {
        "email": EMAIL,
        "password": PASSWORD,
        "device_id": device_id,
        "os": "android",
    }
    s = requests.Session()
    s.trust_env = False
    r = s.post(BASE + "/api/v0/users/login", headers=HEADERS,
               data=json.dumps(body).encode(), timeout=30)
    return r.status_code, r.text[:400]


def main():
    for name, dev in CASES:
        try:
            code, text = post_login(dev)
        except Exception as exc:  # noqa: BLE001
            print(f"{name:14s} EXC {type(exc).__name__}: {exc}")
            time.sleep(15)
            continue
        print(f"{name:14s} HTTP {code}  {text}")
        time.sleep(15)


if __name__ == "__main__":
    os.environ.pop("HTTP_PROXY", None)
    os.environ.pop("HTTPS_PROXY", None)
    main()
