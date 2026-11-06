"""按网页端（chat.deepseek.com）真实请求格式登录。

网页端关键差异（来自 work/web_main.js 模块 55652 / 40093 / 6594）：
- 头 x-device-id = UUID v4（与 body.device_id 同值），x-device-model = ""
- 头 x-client-platform = "web"，x-client-version = "2.7.0"
- body 必须同时带 mobile 与 area_code（邮箱登录时置空串）
- os = "web"
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
import sys
import uuid

import requests

BASE = "https://chat.deepseek.com"
EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def build(device_id):
    headers = {
        "User-Agent": UA,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Content-Type": "application/json",
        "Origin": BASE,
        "Referer": BASE + "/",
        "x-client-bundle-id": "com.deepseek.chat",
        "x-client-platform": "web",
        "x-client-version": "2.7.0",
        "x-client-locale": "zh_CN",
        "x-client-timezone-offset": "28800",
        "x-device-id": device_id,
        "x-device-model": "",
    }
    body = {
        "email": EMAIL,
        "password": PASSWORD,
        "device_id": device_id,
        "os": "web",
        "credential_id": "",
    }
    return headers, body


def main():
    device_id = str(uuid.uuid4())
    headers, body = build(device_id)
    print("device_id =", device_id)
    s = requests.Session()
    s.trust_env = False
    r = s.post(BASE + "/api/v0/users/login", headers=headers,
               data=json.dumps(body).encode(), timeout=30)
    print("HTTP", r.status_code)
    print(r.text[:800])
    for k, v in r.headers.items():
        if k.lower() in ("x-ds-trace-id", "x-ds-served-by", "server", "set-cookie"):
            print(f"  {k}: {v[:120]}")


if __name__ == "__main__":
    sys.exit(main())
