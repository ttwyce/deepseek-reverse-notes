"""补齐 hif / trace-id 等头，直连验证是否解除 RISK_DEVICE_DETECTED。"""
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

EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")
DEV = "8f2a1b3c-4d5e-6f70-8192-a3b4c5d6e7f8"
UA_DALVIK = "Dalvik/2.1.0 (Linux; U; Android 14; Pixel 6 Build/UQ1A.240205.004)"
UA_CHROME = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
PROXY = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}


def get_hif():
    out = {}
    for name in ("dliq", "leim"):
        for ua in (UA_CHROME, UA_DALVIK):
            try:
                r = requests.get(
                    f"https://hif-{name}.deepseek.com/query",
                    headers={"User-Agent": ua, "Referer": "https://chat.deepseek.com/"},
                    proxies=PROXY,
                    timeout=20,
                )
                j = r.json()
                v = (j.get("biz_data") or {}).get("value")
                if v:
                    out["x-hif-" + name] = v
                    print(f"hif-{name} ok (ttl={r.headers.get('x-hif-ttl')})")
                    break
                print(f"hif-{name} 无 value: {r.text[:120]}")
            except Exception as e:  # noqa: BLE001
                print(f"hif-{name} err: {e}")
    return out


def login(tag, ua, extra):
    h = {
        "User-Agent": ua,
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
    h.update(extra)
    body = {"email": EMAIL, "password": PASSWORD, "device_id": DEV, "os": "android"}
    r = requests.post(
        "https://chat.deepseek.com/api/v0/users/login",
        data=json.dumps(body),
        headers=h,
        timeout=30,
    )
    print(f"[{tag}] {r.status_code} {r.text[:220]}")
    time.sleep(3)


def main():
    hif = get_hif()
    login("dalvik+hif", UA_DALVIK, hif)
    login("chrome+hif", UA_CHROME, hif)
    return 0


if __name__ == "__main__":
    sys.exit(main())
