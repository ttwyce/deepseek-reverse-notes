# -*- coding: utf-8 -*-
"""对比实验：
A) 原样重放浏览器捕获的加密请求（body + x-request-encryption-key 全量）
B) 用同一算法（key||iv 32B -> RSA-OAEP-SHA256，AES-128-CBC，公钥 B）自建加密请求
C) 对照：同参数但明文 JSON

目的：确认「加密请求体」是否是 11 与 14 的分界。
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



import base64
import json
import os
import uuid

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

WORK = r"F:\dshh\deepseeka\work"
URL = "https://chat.deepseek.com/api/v0/users/login"
EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")

PUBKEY_B64 = (
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0RLAhx1TOJhAQBHS1LHXlnkfOg86O+uh"
    "smKWNNkmugVrRqO6cl13SnjBs2otRYZGJd50xpBG4We2i6/oCJCwxA/49YZfIwaeDmTx+WBIN7qrw"
    "hwP7vGCi6Osesmn/Ddgdye6mifYkRpRMonQjGY6VPaUMTw1jjOAIKph5YZn0bDVmGLvs5eH6CoQYH"
    "M5/Z1Nfhj36VL28eZi3elJHoz/L6Tzi2wY1rCYqYHfepq3Ysy8y5Y5BeFJXN60RYLlbs+MRC+2kyJ"
    "qcfApUnn1O/W2om9dhxc6Rc5dqas1YB4X4CWCttrKk/suhpIx9zpQY9kqtotbe5zweYaKv0rCVeqx8"
    "wIDAQAB"
)


def load_pubkey():
    der = base64.b64decode(PUBKEY_B64)
    return serialization.load_der_public_key(der)


def encrypt_body(plain: bytes) -> tuple[str, bytes]:
    """与网页 eR / Android e8b.x 完全一致：key||iv(32B) RSA-OAEP-SHA256，body AES-128-CBC。"""
    key = os.urandom(16)
    iv = os.urandom(16)
    blob = key + iv
    pub = load_pubkey()
    wrapped = pub.encrypt(
        blob,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                     algorithm=hashes.SHA256(), label=None),
    )
    header = base64.b64encode(wrapped).decode()
    padder = __import__("cryptography.hazmat.primitives.padding",
                        fromlist=["padding"]).PKCS7(128).padder()
    padded = padder.update(plain) + padder.finalize()
    enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return header, enc.update(padded) + enc.finalize()


def base_headers(device_id: str) -> dict[str, str]:
    return {
        "accept": "*/*",
        "accept-language": "zh-CN",
        "content-type": "application/json",
        "origin": "https://chat.deepseek.com",
        "referer": "https://chat.deepseek.com/sign_in",
        "user-agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36"),
        "x-client-bundle-id": "com.deepseek.chat",
        "x-client-locale": "zh_CN",
        "x-client-platform": "web",
        "x-client-version": "2.7.0",
        "x-client-timezone-offset": "28800",
        "x-device-id": device_id,
        "x-device-model": "",
    }


def main() -> None:
    sess = requests.Session()
    sess.trust_env = False

    # ---- A) 原样重放浏览器捕获的请求 ----
    with open(WORK + r"\pw_login_request.json", encoding="utf-8") as fh:
        cap = json.load(fh)[0]
    print("=== A) replay browser request ===")
    hdr = dict(cap["headers"])
    hdr.pop("content-length", None)
    body = base64.b64decode(cap["body_b64"])
    print("key header len:", len(hdr.get("x-request-encryption-key", "")),
          "body len:", len(body))
    r = sess.post(URL, data=body, headers=hdr, timeout=30)
    print("status:", r.status_code, r.text[:400])

    # ---- B) 自建加密请求 ----
    print("\n=== B) self-built encrypted request ===")
    device_id = str(uuid.uuid4())
    payload = {"email": EMAIL, "password": PASSWORD,
               "device_id": device_id, "os": "web", "credential_id": ""}
    plain = json.dumps(payload, separators=(",", ":")).encode()
    print("plain:", plain.decode())
    key_hdr, ct = encrypt_body(plain)
    h = base_headers(device_id)
    h["x-request-encryption-key"] = key_hdr
    print("key header len:", len(key_hdr), "cipher len:", len(ct))
    r = sess.post(URL, data=ct, headers=h, timeout=30)
    print("status:", r.status_code, r.text[:400])

    # ---- C) 对照：同参数明文 ----
    print("\n=== C) plaintext control ===")
    device_id2 = str(uuid.uuid4())
    h2 = base_headers(device_id2)
    payload2 = {"email": EMAIL, "password": PASSWORD,
                "device_id": device_id2, "os": "web", "credential_id": ""}
    r = sess.post(URL, json=payload2, headers=h2, timeout=30)
    print("status:", r.status_code, r.text[:400])


if __name__ == "__main__":
    main()
