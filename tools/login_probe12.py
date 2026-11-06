"""登录风控矩阵：os 字段取值 × x-client-platform 组合。"""
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


def post(os_val, platform, extra=None):
    h = {
        "User-Agent": UA,
        "Accept": "*/*",
        "Content-Type": "application/json",
        "Origin": "https://chat.deepseek.com",
        "Referer": "https://chat.deepseek.com/",
        "x-client-platform": platform,
        "x-client-version": "2.7.1",
        "x-client-bundle-id": "com.deepseek.chat",
        "x-client-locale": "zh_CN",
        "x-client-timezone-offset": "28800",
        "x-device-model": "Pixel 6",
        "x-ds-trace-id": str(uuid.uuid4()),
    }
    body = {"email": EMAIL, "password": PASSWORD, "device_id": DEV}
    if os_val is not None:
        body["os"] = os_val
    if extra:
        body.update(extra)
    s = creq.Session(impersonate="chrome")
    r = s.post(URL, data=json.dumps(body), headers=h, timeout=30)
    return r.status_code, r.text[:220]


def main():
    cases = [
        ("android", "android", None),
        ("ios", "ios", None),
        ("web", "web", None),
        ("h5", "web", None),
        ("windows", "windows", None),
        ("mac", "mac", None),
        ("pc", "web", None),
    ]
    for osv, plat, extra in cases:
        try:
            code, txt = post(osv, plat, extra)
        except Exception as e:  # noqa: BLE001
            code, txt = -1, f"EXC {e}"
        print(f"os={osv:8s} platform={plat:8s} -> {code} {txt}")
        time.sleep(5)


if __name__ == "__main__":
    main()
