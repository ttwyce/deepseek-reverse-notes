"""DeepSeek 纯协议登录推进：
A) 探测 create_guest_challenge 对 login 的 target_path 变体（此前 /api/v0/users/login 返回 INVALID_TARGET_PATH）
B) 按 App 启动序列预热设备画像，再尝试登录（观察 biz_code 11 是否变化）
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
import time
import uuid

sys.path.insert(0, r"F:\dshh\deepseeka\tools")
import requests
from deepseek_pow import API, HEADERS, get_guest_challenge, build_pow_header

EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")
DEVICE_ID = uuid.uuid4().hex


def hdr(extra=None):
    h = dict(HEADERS)
    h["x-ds-trace-id"] = str(uuid.uuid4())
    if extra:
        h.update(extra)
    return h


def show(tag, r):
    print(f"  {tag:46s} HTTP {r.status_code}  {r.text[:220]}")


def part_a():
    print("=== A) create_guest_challenge target_path 变体 ===")
    for tp in ["/v0/users/login", "/api/v0/users/login", "/users/login",
               "/v0/users/login_by_mobile_sms", "/api/v0/users/login_by_mobile_sms",
               "/v0/users/register", "/v0/users/create_email_verification_code"]:
        try:
            r = requests.post(API + "/api/v0/users/create_guest_challenge",
                              headers=hdr(), json={"target_path": tp}, timeout=20)
            d = r.json()
            ok = (d.get("data") or {}).get("biz_code") == 0
            print(f"  {tp:46s} biz_code={((d.get('data') or {}).get('biz_code'))} "
                  f"{((d.get('data') or {}).get('biz_msg'))} {'✅' if ok else ''}")
        except Exception as e:
            print(f"  {tp:46s} 异常 {e}")
        time.sleep(2)


def part_b():
    print("\n=== B) 预热设备画像 + 登录 ===")
    s = requests.Session()
    h = hdr()

    warm = [
        ("GET", "/api/v0/ip_to_country_code", None),
        ("GET", "/api/v0/client/settings", None),
        ("GET", "/api/v0/check_client_update", None),
        ("GET", "/api/v0/users/current", None),
    ]
    for m, p, body in warm:
        try:
            r = s.request(m, API + p, headers=h, json=body, timeout=20)
            show(p, r)
        except Exception as e:
            print(f"  {p:46s} 异常 {e}")
        time.sleep(2)

    print("  --- 登录（带预热后的 cookie） ---")
    body = {"email": EMAIL, "password": PASSWORD, "device_id": DEVICE_ID, "os": "android"}
    r = s.post(API + "/api/v0/users/login", headers=h, json=body, timeout=20)
    show("login(os=android)", r)
    time.sleep(2)

    print("  --- 登录（os=web + credential_id 空串） ---")
    body = {"email": EMAIL, "password": PASSWORD, "device_id": DEVICE_ID,
            "os": "web", "credential_id": ""}
    r = s.post(API + "/api/v0/users/login", headers=h, json=body, timeout=20)
    show("login(os=web,credential_id='')", r)


if __name__ == "__main__":
    part_a()
    part_b()
