"""DeepSeek 纯协议登录探针 —— 第一步：不处理验证码，直接发原始登录请求看服务端反应。

用法：
  .venv\\Scripts\\python.exe tools\\login_probe.py
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


import base64
import json
import os
import sys
import uuid

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# bb.java:45 主公钥（请求体加密）
RSA_PUB_B64 = (
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAo2wegFXo1m3LGL5mWHXe3s2+tuxutbxwRQRO3RJO6Xjengngpkq"
    "tq0CfkZVdQyMRIR+9nU5xr26swsEbnwG9keuW4ZF8iAPfTobFT5Dxo0Pkya2Q6i+3jBnnC+MdWlSWuW2pJIX0O+78kmB6ZtXxnf"
    "/KmUBa9s6ufFcisgnH1tdpbjwRvzcUz4+zDIneEL7fZlB+nzo258F/oYfqECPRRJRLgDzFYfDd5K22K3grhSTpIvdaYAUe4gyIz/DHL"
    "uo+fIeEeGeTcy2hp4pqaT6ctlh7iHDbcSXvy5wqmVwI4M8atyLcl0/osb7JErbu/nuTc8okGCKzt3D8RTwHa/Z2BQIDAQAB"
)

BASE = "https://chat.deepseek.com"
PROXIES = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}

EMAIL = os.environ.get("DS_EMAIL", _cred("DS_EMAIL"))
PASSWORD = os.environ.get("DS_PASSWORD", _cred("DS_PASSWORD"))
DEVICE_ID = os.environ.get("DS_DEVICE_ID") or str(uuid.uuid4())


def load_pub():
    pem = (
        b"-----BEGIN PUBLIC KEY-----\n"
        + "\n".join(RSA_PUB_B64[i:i + 64] for i in range(0, len(RSA_PUB_B64), 64)).encode()
        + b"\n-----END PUBLIC KEY-----\n"
    )
    return serialization.load_pem_public_key(pem)


def encrypt_body(obj, pub):
    """随机 AES-128 key+IV -> RSA-OAEP(SHA-256) 加密 key||iv -> Base64；body 用 AES-CBC/PKCS5 密文。"""
    key = os.urandom(16)
    iv = os.urandom(16)
    ct = pub.encrypt(
        key + iv,
        padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
    )
    enc_key = base64.b64encode(ct).decode()
    raw = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode()
    pad = 16 - len(raw) % 16
    raw += bytes([pad]) * pad
    enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return enc_key, enc.update(raw) + enc.finalize()


def base_headers(enc_key):
    return {
        "Referer": "https://chat.deepseek.com",
        "x-client-platform": "android",
        "x-client-version": "2.7.1",
        "x-client-locale": "zh_CN",
        "x-client-bundle-id": "com.deepseek.chat",
        "x-client-timezone-offset": "28800",
        "x-device-model": "Pixel 6",
        "x-request-encryption-key": enc_key,
        "Content-Type": "application/json",
        "Accept": "*/*",
        "User-Agent": "okhttp/4.12.0",
    }


def main():
    pub = load_pub()
    payload = {
        "email": EMAIL,
        "password": PASSWORD,
        "device_id": DEVICE_ID,
    }
    enc_key, body = encrypt_body(payload, pub)
    h = base_headers(enc_key)
    url = BASE + "/api/v0/users/login"
    print("== POST", url)
    print("== device_id:", DEVICE_ID)
    print("== 明文 body:", json.dumps(payload, ensure_ascii=False))
    try:
        r = requests.post(url, data=body, headers=h, proxies=PROXIES, timeout=30)
    except Exception as e:
        print("!! 请求异常:", type(e).__name__, e)
        return 1
    print("== HTTP", r.status_code)
    print("== 响应头:")
    for k, v in r.headers.items():
        print("   ", k, "=", v)
    print("== 响应体:")
    print(r.text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
