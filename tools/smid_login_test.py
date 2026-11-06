# -*- coding: utf-8 -*-
"""验证：用数美 SDK 生成的 device_id（88 字符 base64）做纯协议加密登录。

device_id 取自浏览器 localStorage 的 .thumbcache_* 值。
字段顺序严格复刻网页端：email, mobile, area_code, password, device_id, os, credential_id
"""
from __future__ import annotations
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

import requests

sys.path.insert(0, r"F:\dshh\deepseeka\tools")
from enc_login_test import PUBKEY_B64, base_headers, encrypt_body  # noqa: E402

URL = "https://chat.deepseek.com/api/v0/users/login"
EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")
WORK = r"F:\dshh\deepseeka\work"

# 来自 pw_hook_encrypt.py 捕获的浏览器明文 device_id
DEV_FROM_HOOK = ("BNaTEWNfiFMdnqIEm6bgYReu82v3DlNH+eFGqTXHGyRxbMKwiK2W2QmI9jXc3qd"
                 "DhyPjyUerU43GzO70hgtlu3g==")


def build_payload(device_id: str, os_name: str = "web") -> bytes:
    payload = {
        "email": EMAIL,
        "mobile": "",
        "area_code": "",
        "password": PASSWORD,
        "device_id": device_id,
        "os": os_name,
        "credential_id": "",
    }
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()


def attempt(label: str, device_id: str, os_name: str = "web") -> None:
    plain = build_payload(device_id, os_name)
    key_hdr, ct = encrypt_body(plain)
    h = base_headers(device_id)
    h["x-request-encryption-key"] = key_hdr
    sess = requests.Session()
    sess.trust_env = False
    r = sess.post(URL, data=ct, headers=h, timeout=30)
    print(f"[{label}] status={r.status_code}")
    print(f"    plain_len={len(plain)} cipher_len={len(ct)}")
    print(f"    {r.text[:300]}")


def main() -> None:
    attempt("A 数美device_id(hook捕获)", DEV_FROM_HOOK, "web")
    attempt("B 同上 os=android", DEV_FROM_HOOK, "android")
    attempt("C 随机UUID对照", "0b7a9658-c0e7-4184-8fa9-4763ae203c32", "web")


if __name__ == "__main__":
    main()
