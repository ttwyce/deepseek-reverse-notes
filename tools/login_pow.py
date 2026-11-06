"""尝试 guest PoW 挑战 + 登录（验证 RISK_DEVICE_DETECTED 是否与 PoW 缺失相关）。"""
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
PASSWORD = _cred("DS_PASSWORD")
DEV = "8f2a1b3c-4d5e-6f70-8192-a3b4c5d6e7f8"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def H():
    return {
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


def solve(challenge_hex, salt, expire_at, difficulty, cap=3_000_000):
    base = f"{salt}_{expire_at}_".encode()
    target = bytes.fromhex(challenge_hex)
    n = min(difficulty, cap)
    for nonce in range(n):
        if hashlib.sha3_256(base + str(nonce).encode()).digest() == target:
            return nonce
    return None


def main():
    delay = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    if delay:
        print(f"冷却 {delay}s ...")
        time.sleep(delay)

    s = creq.Session(impersonate="chrome")
    r = s.post(
        "https://chat.deepseek.com/api/v0/users/create_guest_challenge",
        data=json.dumps({"target_path": "/api/v0/users/login"}),
        headers=H(),
        timeout=30,
    )
    print("challenge:", r.status_code, r.text[:500])
    try:
        g = r.json()["data"]["biz_data"]["guest_challenge"]
    except Exception:  # noqa: BLE001
        print("未拿到 challenge，终止")
        return 1

    print("challenge 对象:", json.dumps(g, ensure_ascii=False)[:400])
    nonce = solve(g["challenge"], g["salt"], g["expire_at"], g["difficulty"])
    print("nonce =", nonce)
    if nonce is None:
        return 1

    sol = {
        "algorithm": g["algorithm"],
        "challenge": g["challenge"],
        "salt": g["salt"],
        "signature": g["signature"],
        "answer": nonce,
        "target_path": "/api/v0/users/login",
    }
    hdr = base64.b64encode(json.dumps(sol, separators=(",", ":")).encode()).decode()
    time.sleep(3)

    h = H()
    h["X-DS-Guest-Pow-Response"] = hdr
    body = {"email": EMAIL, "password": PASSWORD, "device_id": DEV, "os": "android"}
    r = s.post(
        "https://chat.deepseek.com/api/v0/users/login",
        data=json.dumps(body),
        headers=h,
        timeout=30,
    )
    print("login+guestpow:", r.status_code, r.text[:300])
    return 0


if __name__ == "__main__":
    sys.exit(main())
