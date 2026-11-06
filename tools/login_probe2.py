"""登录请求体 schema 探测：补 os 字段，比较明文与加密两条路径。"""
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
import time
import uuid

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

PROXIES = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
PUB_B = (
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0RLAhx1TOJhAQBHS1LHXlnkfOg86O+uhsmKWNNkmugVrRqO6cl13"
    "SnjBs2otRYZGJd50xpBG4We2i6/oCJCwxA/49YZfIwaeDmTx+WBIN7qrwhwP7vGCi6Osesmn/Ddgdye6mifYkRpRMonQjGY6VPaUMTw"
    "1jjOAIKph5YZn0bDVmGLvs5eH6CoQYHM5/Z1Nfhj36VL28eZi3elJHoz/L6Tzi2wY1rCYqYHfepq3Ysy8y5Y5BeFJXN60RYLlbs+MRC"
    "+2kyJqcfApUnn1O/W2om9dhxc6Rc5dqas1YB4X4CWCttrKk/suhpIx9zpQY9kqtotbe5zweYaKv0rCVeqx8wIDAQAB"
)
EMAIL = os.environ.get("DS_EMAIL", _cred("DS_EMAIL"))
PASSWORD = os.environ.get("DS_PASSWORD", _cred("DS_PASSWORD"))
DEV = "b8f4a1c2d3e4f5061728394a5b6c7d8e"


def pub():
    pem = (
        b"-----BEGIN PUBLIC KEY-----\n"
        + "\n".join(PUB_B[i:i + 64] for i in range(0, len(PUB_B), 64)).encode()
        + b"\n-----END PUBLIC KEY-----\n"
    )
    return serialization.load_pem_public_key(pem)


def headers(extra=None):
    h = {
        "User-Agent": UA,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Origin": "https://chat.deepseek.com",
        "Referer": "https://chat.deepseek.com/",
        "x-client-platform": "android",
        "x-client-version": "2.7.1",
        "x-client-bundle-id": "com.deepseek.chat",
        "x-client-locale": "zh_CN",
        "x-client-timezone-offset": "28800",
        "x-device-model": "Pixel 6",
        "Content-Type": "application/json",
    }
    if extra:
        h.update(extra)
    return h


def encrypt(plain):
    key, iv = os.urandom(16), os.urandom(16)
    ek = base64.b64encode(
        pub().encrypt(
            key + iv,
            padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
        )
    ).decode()
    pad = 16 - len(plain) % 16
    raw = plain + bytes([pad]) * pad
    enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return ek, enc.update(raw) + enc.finalize()


def send(tag, data, extra=None):
    r = requests.post(
        "https://chat.deepseek.com/api/v0/users/login",
        data=data,
        headers=headers(extra),
        proxies=PROXIES,
        timeout=30,
    )
    print(f"---- {tag}: HTTP {r.status_code}\n{r.text[:800]}\n")
    return r


def main():
    base = {"email": EMAIL, "password": PASSWORD, "device_id": DEV, "os": "android"}
    plain = json.dumps(base, separators=(",", ":")).encode()

    send("A 明文+os", plain)
    time.sleep(1.5)

    ek, ct = encrypt(plain)
    send("B 密文+os+key", ct, {"x-request-encryption-key": ek})
    return 0


if __name__ == "__main__":
    sys.exit(main())
