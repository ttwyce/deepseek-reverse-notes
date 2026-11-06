"""对比出口 IP 与 hif 头对 RISK_DEVICE_DETECTED 的影响。"""
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


def headers(extra=None):
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
    if extra:
        h.update(extra)
    return h


def get_hif():
    out = {}
    for name in ("dliq", "leim"):
        try:
            r = requests.get(
                f"https://hif-{name}.deepseek.com/query",
                headers={"User-Agent": UA},
                proxies=PROXIES,
                timeout=20,
            )
            out["x-hif-" + name] = r.json()["biz_data"]["value"]
        except Exception as e:  # noqa: BLE001
            print(f"hif-{name} 获取失败: {e}")
    return out


def run(tag, body, proxies, extra=None):
    r = requests.post(
        "https://chat.deepseek.com/api/v0/users/login",
        data=json.dumps(body),
        headers=headers(extra),
        proxies=proxies,
        timeout=30,
    )
    print(f"{tag}: {r.status_code} {r.text[:220]}")
    time.sleep(1.2)


def main():
    body = {"email": EMAIL, "password": PASSWORD, "device_id": str(uuid.uuid4()), "os": "android"}
    run("直连/无hif", body, None)
    hif = get_hif()
    print("hif 头:", {k: v[:24] + "..." for k, v in hif.items()})
    run("直连/带hif", body, None, hif)
    run("代理/带hif", body, PROXIES, hif)
    return 0


if __name__ == "__main__":
    sys.exit(main())
