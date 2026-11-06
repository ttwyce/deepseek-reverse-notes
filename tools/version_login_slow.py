"""慢速单次探测：登录限流按账号维度计数（40029），必须长间隔。
依次用不同 x-client-version 尝试登录，遇到非 11 / 非 40029 的结果立即停止。"""
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
VERSIONS = ["3.0.0", "2.9.5", "2.8.5", "2.7.5"]
GAP = 200


def hdr(ver):
    h = dict(HEADERS)
    h["x-client-version"] = ver
    h["x-ds-trace-id"] = str(uuid.uuid4())
    return h


def main():
    body = {"email": EMAIL, "password": PASSWORD, "device_id": DEVICE_ID, "os": "android"}
    for ver in VERSIONS:
        time.sleep(GAP)
        try:
            r = requests.post(API + "/api/v0/users/login", headers=hdr(ver), json=body, timeout=25)
            txt = r.text[:220]
        except Exception as e:
            txt = f"异常 {e}"
        print(f"[{time.strftime('%H:%M:%S')}] ver={ver:6s} {txt}", flush=True)
        if "40029" not in txt and '"biz_code":11' not in txt:
            print("!!! 结果不同，停止探测", flush=True)
            break
    print("done", flush=True)


if __name__ == "__main__":
    main()
