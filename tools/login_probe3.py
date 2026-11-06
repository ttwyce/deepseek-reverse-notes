"""探测 device_id 格式 / os 取值 / 额外字段对 RISK_DEVICE_DETECTED 的影响。"""
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

import requests

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
PROXIES = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")


def headers():
    return {
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


def run(tag, body):
    r = requests.post(
        "https://chat.deepseek.com/api/v0/users/login",
        data=json.dumps(body),
        headers=headers(),
        proxies=PROXIES,
        timeout=30,
    )
    print(f"{tag}: {r.status_code} {r.text[:220]}")
    time.sleep(1.2)


def main():
    run("uuid36/os=android", {"email": EMAIL, "password": PASSWORD, "device_id": str(uuid.uuid4()), "os": "android"})
    run("uuid36/os=Android", {"email": EMAIL, "password": PASSWORD, "device_id": str(uuid.uuid4()), "os": "Android"})
    run(
        "uuid36/+device_name",
        {
            "email": EMAIL,
            "password": PASSWORD,
            "device_id": str(uuid.uuid4()),
            "os": "android",
            "device_name": "Pixel 6",
            "os_version": "14",
            "client_version": "2.7.1",
        },
    )
    fixed = "8f2a1b3c-4d5e-6f70-8192-a3b4c5d6e7f8"
    run("fixed-uuid1", {"email": EMAIL, "password": PASSWORD, "device_id": fixed, "os": "android"})
    run("fixed-uuid2", {"email": EMAIL, "password": PASSWORD, "device_id": fixed, "os": "android"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
