"""UA 与 x-client-platform 一致性对设备风控的影响（直连，低频）。"""
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
UAS = [
    ("okhttp", "okhttp/4.12.0"),
    ("dalvik", "Dalvik/2.1.0 (Linux; U; Android 14; Pixel 6 Build/UQ1A.240205.004)"),
    ("nokia", "com.deepseek.chat/2.7.1 (Linux; Android 14; Pixel 6)"),
]


def main():
    for tag, ua in UAS:
        h = {
            "User-Agent": ua,
            "Content-Type": "application/json",
            "x-client-platform": "android",
            "x-client-version": "2.7.1",
            "x-client-bundle-id": "com.deepseek.chat",
            "x-client-locale": "zh_CN",
            "x-client-timezone-offset": "28800",
            "x-device-model": "Pixel 6",
        }
        body = {"email": EMAIL, "password": PASSWORD, "device_id": DEV, "os": "android"}
        r = requests.post(
            "https://chat.deepseek.com/api/v0/users/login",
            data=json.dumps(body),
            headers=h,
            timeout=30,
        )
        print(f"{tag}: {r.status_code} {r.text[:200]}")
        time.sleep(3)
    return 0


if __name__ == "__main__":
    sys.exit(main())
