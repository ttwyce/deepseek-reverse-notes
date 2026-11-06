"""冷却 30 分钟后单次登录，用于判定 biz_code 11 是否为高频尝试触发的临时风控。

结果追加写入 work\login_wait.log。
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
import time
import uuid

import requests

BASE = "https://chat.deepseek.com"
EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")
LOG = r"F:\dshh\deepseeka\work\login_wait.log"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def attempt(tag, os_value, with_cred):
    device_id = str(uuid.uuid4())
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
    body = {"email": EMAIL, "password": PASSWORD,
            "device_id": device_id, "os": os_value}
    if with_cred:
        body["credential_id"] = ""
    s = requests.Session()
    s.trust_env = False
    try:
        r = s.post(BASE + "/api/v0/users/login", headers=headers,
                   data=json.dumps(body).encode(), timeout=30)
        line = f"[{time.strftime('%H:%M:%S')}] {tag} os={os_value} cred={with_cred} HTTP {r.status_code} {r.text[:300]}"
    except Exception as exc:  # noqa: BLE001
        line = f"[{time.strftime('%H:%M:%S')}] {tag} EXC {type(exc).__name__}: {exc}"
    print(line)
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def main():
    wait = 1800
    print(f"waiting {wait}s ...")
    time.sleep(wait)
    attempt("after30m", "web", True)
    time.sleep(120)
    attempt("after30m-2", "android", False)


if __name__ == "__main__":
    main()
