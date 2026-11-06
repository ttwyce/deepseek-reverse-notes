"""测试邮箱验证码通道：guest pow -> create_email_verification_code。"""
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


import base64
import hashlib
import json
import sys
import time
import uuid

from curl_cffi import requests as creq

EMAIL = _cred("DS_EMAIL")
DEV = "8f2a1b3c-4d5e-6f70-8192-a3b4c5d6e7f8"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
TARGET = "/api/v0/users/create_email_verification_code"


def H():
    return {
        "User-Agent": UA,
        "Accept": "*/*",
        "Content-Type": "application/json",
        "Origin": "https://chat.deepseek.com",
        "Referer": "https://chat.deepseek.com/",
        "x-client-platform": "android",
        "x-client-version": "2.7.1",
        "x-client-bundle-id": "com.deepseek.chat",
        "x-client-locale": "zh_CN",
        "x-client-timezone-offset": "28800",
        "x-device-model": "Pixel 6",
        "x-ds-trace-id": str(uuid.uuid4()),
    }


def solve(ch, salt, exp, diff, cap=8_000_000):
    base = f"{salt}_{exp}_".encode()
    tgt = bytes.fromhex(ch)
    for n in range(min(diff, cap)):
        if hashlib.sha3_256(base + str(n).encode()).digest() == tgt:
            return n
    return None


def main():
    s = creq.Session(impersonate="chrome")
    r = s.post(
        "https://chat.deepseek.com/api/v0/users/create_guest_challenge",
        data=json.dumps({"target_path": TARGET}),
        headers=H(),
        timeout=30,
    )
    print("challenge:", r.status_code, r.text[:400])
    try:
        c = r.json()["data"]["biz_data"]["challenge"]
    except Exception:  # noqa: BLE001
        return 1
    print("  difficulty:", c.get("difficulty"), "algo:", c.get("algorithm"))
    n = solve(c["challenge"], c["salt"], c["expire_at"], c["difficulty"])
    print("  nonce:", n)
    if n is None:
        return 1
    sol = {
        "algorithm": c["algorithm"],
        "challenge": c["challenge"],
        "salt": c["salt"],
        "signature": c["signature"],
        "answer": n,
        "target_path": TARGET,
    }
    pow_hdr = base64.b64encode(json.dumps(sol, separators=(",", ":")).encode()).decode()
    time.sleep(2)
    for scen in ("login", "register", None):
        h = H()
        h["X-DS-Guest-Pow-Response"] = pow_hdr
        body = {"email": EMAIL, "locale": "zh_CN", "device_id": DEV}
        if scen:
            body["scenario"] = scen
        r2 = s.post(
            "https://chat.deepseek.com" + TARGET,
            data=json.dumps(body),
            headers=h,
            timeout=30,
        )
        print(f"scenario={scen}: {r2.status_code} {r2.text[:300]}")
        time.sleep(6)
    return 0


if __name__ == "__main__":
    sys.exit(main())
