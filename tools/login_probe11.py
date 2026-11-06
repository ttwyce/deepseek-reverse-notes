"""打印登录响应头，寻找 X-Auth-Block 等风控提示。"""
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


def main():
    delay = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    if delay:
        print(f"冷却 {delay}s ...")
        time.sleep(delay)
    h = {
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
    body = {"email": EMAIL, "password": PASSWORD, "device_id": DEV, "os": "android"}
    r = creq.post(
        "https://chat.deepseek.com/api/v0/users/login",
        data=json.dumps(body),
        headers=h,
        impersonate="chrome",
        timeout=30,
    )
    print("STATUS", r.status_code)
    for k, v in r.headers.items():
        print(f"  {k}: {v}")
    print("BODY", r.text[:300])
    return 0


if __name__ == "__main__":
    sys.exit(main())
