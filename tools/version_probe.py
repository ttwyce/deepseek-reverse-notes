"""验证假设：服务端已对旧客户端版本（x-client-version=2.7.1）执行风控，
返回 v2.7.1 客户端不认识的 biz_code 11。试更高版本号 + 查询最新版本。"""
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


import sys
import time
import uuid

sys.path.insert(0, r"F:\dshh\deepseeka\tools")
import requests
from deepseek_pow import API, HEADERS

EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")
DEVICE_ID = uuid.uuid4().hex


def hdr(ver):
    h = dict(HEADERS)
    h["x-client-version"] = ver
    h["x-ds-trace-id"] = str(uuid.uuid4())
    return h


def main():
    print("=== 1) 查询最新客户端版本 ===")
    for q in ["", "?current_version=2.7.1", "?current_version=2.7.1&platform=android",
              "?version=2.7.1&os=android"]:
        try:
            r = requests.get(API + "/api/v0/check_client_update" + q, headers=hdr("2.7.1"), timeout=20)
            print(f"  {q or '(无参)':44s} HTTP {r.status_code}  {r.text[:260]}")
        except Exception as e:
            print(f"  {q:44s} 异常 {e}")
        time.sleep(2)

    print("\n=== 2) 用不同 x-client-version 登录 ===")
    body = {"email": EMAIL, "password": PASSWORD, "device_id": DEVICE_ID, "os": "android"}
    for ver in ["2.7.1", "2.8.0", "2.9.0", "3.0.0", "3.1.0", "3.2.0"]:
        try:
            r = requests.post(API + "/api/v0/users/login", headers=hdr(ver), json=body, timeout=20)
            print(f"  x-client-version={ver:8s} HTTP {r.status_code}  {r.text[:200]}")
        except Exception as e:
            print(f"  x-client-version={ver:8s} 异常 {e}")
        time.sleep(3)


if __name__ == "__main__":
    main()
