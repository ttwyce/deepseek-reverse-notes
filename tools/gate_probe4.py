"""关键结论验证：WAF 按 UA 指纹拦截 okhttp；改用浏览器 UA 后 API 是否可达。"""
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

PROXIES = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}

RSA_PUB_B64 = (
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAo2wegFXo1m3LGL5mWHXe3s2+tuxutbxwRQRO3RJO6Xjengngpkq"
    "tq0CfkZVdQyMRIR+9nU5xr26swsEbnwG9keuW4ZF8iAPfTobFT5Dxo0Pkya2Q6i+3jBnnC+MdWlSWuW2pJIX0O+78kmB6ZtXxnf"
    "/KmUBa9s6ufFcisgnH1tdpbjwRvzcUz4+zDIneEL7fZlB+nzo258F/oYfqECPRRJRLgDzFYfDd5K22K3grhSTpIvdaYAUe4gyIz/DHL"
    "uo+fIeEeGeTcy2hp4pqaT6ctlh7iHDbcSXvy5wqmVwI4M8atyLcl0/osb7JErbu/nuTc8okGCKzt3D8RTwHa/Z2BQIDAQAB"
)

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

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
    key, iv = os.urandom(16), os.urandom(16)
    ct = pub.encrypt(key + iv, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    raw = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode()
    pad = 16 - len(raw) % 16
    raw += bytes([pad]) * pad
    enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return base64.b64encode(ct).decode(), enc.update(raw) + enc.finalize()


def headers(extra=None):
    h = {
        "User-Agent": BROWSER_UA,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Origin": "https://chat.deepseek.com",
        "Referer": "https://chat.deepseek.com/",
        "sec-ch-ua": '"Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "x-client-platform": "android",
        "x-client-version": "2.7.1",
        "x-client-bundle-id": "com.deepseek.chat",
        "x-client-locale": "zh_CN",
        "x-client-timezone-offset": "28800",
        "x-device-model": "Pixel 6",
    }
    if extra:
        h.update(extra)
    return h


def brief(tag, r):
    print(f"---- {tag}: HTTP {r.status_code} ct={r.headers.get('Content-Type')} block={r.headers.get('Block-Event-Id')}")
    print("     body:", r.text[:800].replace("\n", " "))
    print()


def main():
    s = requests.Session()
    s.headers.update(headers())

    r = s.get("https://chat.deepseek.com/api/v0/client/settings", proxies=PROXIES, timeout=30)
    brief("1 GET client/settings (浏览器UA)", r)

    pub = load_pub()
    payload = {"email": EMAIL, "password": PASSWORD, "device_id": DEVICE_ID}
    enc_key, body = encrypt_body(payload, pub)
    r2 = s.post(
        "https://chat.deepseek.com/api/v0/users/login",
        data=body,
        headers=headers({"x-request-encryption-key": enc_key, "Content-Type": "application/json"}),
        proxies=PROXIES,
        timeout=30,
    )
    brief("2 POST users/login (加密体, 浏览器UA)", r2)
    print("   device_id:", DEVICE_ID)
    print("   cookies:", s.cookies.get_dict())
    return 0


if __name__ == "__main__":
    sys.exit(main())
