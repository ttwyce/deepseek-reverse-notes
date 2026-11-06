"""判定 RISK_DEVICE_DETECTED 是否与密码正确性相关。"""
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
import uuid

from curl_cffi import requests as creq

EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")
DEV = "8f2a1b3c-4d5e-6f70-8192-a3b4c5d6e7f8"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def H():
    return {
        "User-Agent": UA,
        "Accept": "*/*",
        "Content-Type": "application/json",
        "x-client-platform": "android",
        "x-client-version": "2.7.1",
        "x-client-bundle-id": "com.deepseek.chat",
        "x-client-locale": "zh_CN",
        "x-client-timezone-offset": "28800",
        "x-device-model": "Pixel 6",
        "x-ds-trace-id": str(uuid.uuid4()),
    }


def login(tag, pwd, impersonate="chrome"):
    body = {"email": EMAIL, "password": pwd, "device_id": DEV, "os": "android"}
    try:
        r = creq.post(
            "https://chat.deepseek.com/api/v0/users/login",
            data=json.dumps(body),
            headers=H(),
            impersonate=impersonate,
            timeout=30,
        )
        print(f"[{tag}] {r.status_code} {r.text[:200]}")
    except Exception as e:  # noqa: BLE001
        print(f"[{tag}] err {e}")
    time.sleep(4)


def main():
    delay = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    if delay:
        print(f"冷却 {delay}s ...")
        time.sleep(delay)
    login("错密码", "wrong_password_123")
    login("正确密码/okhttp指纹", PASSWORD, "okhttp5" if True else "chrome")
    login("正确密码/chrome", PASSWORD, "chrome")
    return 0


if __name__ == "__main__":
    sys.exit(main())
