"""定位 REQUEST_DECRYPT_FAILED 原因：公钥 A/B × body 编码（裸字节 / base64）矩阵测试。"""
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
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

PUB_A = (  # bb.java:45
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAo2wegFXo1m3LGL5mWHXe3s2+tuxutbxwRQRO3RJO6Xjengngpkq"
    "tq0CfkZVdQyMRIR+9nU5xr26swsEbnwG9keuW4ZF8iAPfTobFT5Dxo0Pkya2Q6i+3jBnnC+MdWlSWuW2pJIX0O+78kmB6ZtXxnf"
    "/KmUBa9s6ufFcisgnH1tdpbjwRvzcUz4+zDIneEL7fZlB+nzo258F/oYfqECPRRJRLgDzFYfDd5K22K3grhSTpIvdaYAUe4gyIz/DHL"
    "uo+fIeEeGeTcy2hp4pqaT6ctlh7iHDbcSXvy5wqmVwI4M8atyLcl0/osb7JErbu/nuTc8okGCKzt3D8RTwHa/Z2BQIDAQAB"
)
PUB_B = (  # p0a.java:53
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0RLAhx1TOJhAQBHS1LHXlnkfOg86O+uhsmKWNNkmugVrRqO6cl13"
    "SnjBs2otRYZGJd50xpBG4We2i6/oCJCwxA/49YZfIwaeDmTx+WBIN7qrwhwP7vGCi6Osesmn/Ddgdye6mifYkRpRMonQjGY6VPaUMTw"
    "1jjOAIKph5YZn0bDVmGLvs5eH6CoQYHM5/Z1Nfhj36VL28eZi3elJHoz/L6Tzi2wY1rCYqYHfepq3Ysy8y5Y5BeFJXN60RYLlbs+MRC"
    "+2kyJqcfApUnn1O/W2om9dhxc6Rc5dqas1YB4X4CWCttrKk/suhpIx9zpQY9kqtotbe5zweYaKv0rCVeqx8wIDAQAB"
)

EMAIL = os.environ.get("DS_EMAIL", _cred("DS_EMAIL"))
PASSWORD = os.environ.get("DS_PASSWORD", _cred("DS_PASSWORD"))
DEVICE_ID = str(uuid.uuid4())


def load_pub(b64):
    pem = (
        b"-----BEGIN PUBLIC KEY-----\n"
        + "\n".join(b64[i:i + 64] for i in range(0, len(b64), 64)).encode()
        + b"\n-----END PUBLIC KEY-----\n"
    )
    return serialization.load_pem_public_key(pem)


def make(pub, obj):
    key, iv = os.urandom(16), os.urandom(16)
    ct = pub.encrypt(key + iv, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    raw = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode()
    pad = 16 - len(raw) % 16
    raw += bytes([pad]) * pad
    enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return base64.b64encode(ct).decode(), enc.update(raw) + enc.finalize()


def headers(enc_key):
    return {
        "User-Agent": BROWSER_UA,
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
        "x-request-encryption-key": enc_key,
        "Content-Type": "application/json",
    }


def attempt(tag, pub_b64, mode):
    pub = load_pub(pub_b64)
    payload = {"email": EMAIL, "password": PASSWORD, "device_id": DEVICE_ID}
    enc_key, ct = make(pub, payload)
    data = ct if mode == "raw" else base64.b64encode(ct)
    try:
        r = requests.post(
            "https://chat.deepseek.com/api/v0/users/login",
            data=data,
            headers=headers(enc_key),
            proxies=PROXIES,
            timeout=30,
        )
    except Exception as e:
        print(f"[{tag}/{mode}] 异常 {type(e).__name__}: {e}")
        return None
    print(f"[{tag}/{mode}] HTTP {r.status_code} -> {r.text[:300]}")
    return r


def main():
    for tag, pub in (("A bb:45", PUB_A), ("B p0a:53", PUB_B)):
        for mode in ("raw", "b64"):
            r = attempt(tag, pub, mode)
            if r is not None and r.status_code == 200 and "40006" not in r.text:
                print(">>> 成功组合:", tag, mode)
                return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
