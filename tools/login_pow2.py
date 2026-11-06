"""尝试 chat/create_pow_challenge 为登录路径取 PoW，带 X-DS-PoW-Response 登录。"""
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


def solve(ch, salt, exp, diff, cap=5_000_000):
    base = f"{salt}_{exp}_".encode()
    tgt = bytes.fromhex(ch)
    for n in range(min(diff, cap)):
        if hashlib.sha3_256(base + str(n).encode()).digest() == tgt:
            return n
    return None


def main():
    delay = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    if delay:
        print(f"冷却 {delay}s ...")
        time.sleep(delay)
    s = creq.Session(impersonate="chrome")
    for path in ("/api/v0/users/login", "/api/v0/chat/completion"):
        r = s.post(
            "https://chat.deepseek.com/api/v0/chat/create_pow_challenge",
            data=json.dumps({"target_path": path}),
            headers=H(),
            timeout=30,
        )
        print(f"challenge[{path}]: {r.status_code} {r.text[:400]}")
        time.sleep(3)
        try:
            c = r.json()["data"]["biz_data"]["challenge"]
        except Exception:  # noqa: BLE001
            continue
        print("  字段:", json.dumps(c, ensure_ascii=False)[:300])
        n = solve(c["challenge"], c["salt"], c["expire_at"], c["difficulty"])
        print("  nonce:", n)
        if n is None:
            continue
        sol = {
            "algorithm": c["algorithm"],
            "challenge": c["challenge"],
            "salt": c["salt"],
            "signature": c["signature"],
            "answer": n,
            "target_path": path,
        }
        hdr = base64.b64encode(json.dumps(sol, separators=(",", ":")).encode()).decode()
        h = H()
        h["X-DS-PoW-Response"] = hdr
        body = {"email": EMAIL, "password": PASSWORD, "device_id": DEV, "os": "android"}
        r2 = s.post(
            "https://chat.deepseek.com/api/v0/users/login",
            data=json.dumps(body),
            headers=h,
            timeout=30,
        )
        print(f"  login+pow: {r2.status_code} {r2.text[:250]}")
        time.sleep(4)
    return 0


if __name__ == "__main__":
    sys.exit(main())
