"""枚举 create_email_verification_code 的 scenario 取值。

PoW 已验证可通过（此前 422 只报缺 turnstile_token 与 scenario），
本脚本固定 email/locale/device_id，逐个尝试 scenario 候选，观察 422 的 loc 变化。
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


import sys
import time

sys.path.insert(0, r"F:\dshh\deepseeka\tools")
import requests
from deepseek_pow import API, HEADERS, get_guest_challenge, build_pow_header

EMAIL = _cred("DS_EMAIL")
TP = "/api/v0/users/create_email_verification_code"

CANDIDATES = [
    "register", "login", "reset_password", "bind_email", "bind",
    "change_password", "set_password", "email_verify", "verify",
    "signup", "register_by_email", "forget_password", "modify_password",
    "add_email", "email_bind", "unbind_email", "delete_account",
]


def main():
    header, nonce = build_pow_header(get_guest_challenge(TP)["data"]["biz_data"]["guest_challenge"])
    print(f"PoW nonce={nonce}")
    h = dict(HEADERS)
    h["X-DS-Guest-Pow-Response"] = header

    for sc in CANDIDATES:
        body = {"email": EMAIL, "locale": "zh_CN", "device_id": "a" * 32,
                "scenario": sc, "turnstile_token": ""}
        try:
            r = requests.post(API + "/api/v0/users/create_email_verification_code",
                              headers=h, json=body, timeout=20)
            print(f"scenario={sc:22s} HTTP {r.status_code}  {r.text[:200]}")
        except Exception as e:
            print(f"scenario={sc:22s} 异常 {e}")
        time.sleep(2)


if __name__ == "__main__":
    main()
