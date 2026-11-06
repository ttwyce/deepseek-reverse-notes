"""直连单次登录探测（用于冷却后低频验证设备风控是否与出口 IP 相关）。"""
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

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")
DEV = "8f2a1b3c-4d5e-6f70-8192-a3b4c5d6e7f8"


def main():
    delay = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    if delay:
        print(f"冷却 {delay}s ...")
        time.sleep(delay)
    body = {"email": EMAIL, "password": PASSWORD, "device_id": DEV, "os": "android"}
    h = {
        "User-Agent": UA,
        "Content-Type": "application/json",
        "Origin": "https://chat.deepseek.com",
        "Referer": "https://chat.deepseek.com/",
        "x-client-platform": "android",
        "x-client-version": "2.7.1",
        "x-client-bundle-id": "com.deepseek.chat",
        "x-client-locale": "zh_CN",
        "x-client-timezone-offset": "28800",
        "x-device-model": "Pixel 6",
    }
    r = requests.post(
        "https://chat.deepseek.com/api/v0/users/login",
        data=json.dumps(body),
        headers=h,
        timeout=30,
    )
    print(r.status_code, dict(r.headers).get("Server"), dict(r.headers).get("Content-Type"))
    print(r.text[:600])
    return 0


if __name__ == "__main__":
    sys.exit(main())
