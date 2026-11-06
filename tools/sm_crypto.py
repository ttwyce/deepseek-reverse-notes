"""数美 getEncryptContent 的 Python 复刻：DES-ECB + ZeroPadding + base64。

逆向依据（work/sm/captcha-sdk.deob.js 偏移 210618 getEncryptContent）：
  key = salt（非空时）；plain = 字符串原样 / 非字符串先 JSON 序列化
  out = DES(key, plain, 9, 0) -> base64Encode
实测等价：cryptography TripleDES(key) + ECB + 明文补 \\0 到 8 的倍数（已对齐则不补）。
"""
import base64
import json
import warnings

from cryptography.hazmat.primitives.ciphers import Cipher, modes

warnings.filterwarnings("ignore")

try:  # cryptography >= 43
    from cryptography.hazmat.decrepit.ciphers.algorithms import TripleDES
except Exception:  # pragma: no cover
    from cryptography.hazmat.primitives.ciphers.algorithms import TripleDES


def _key_bytes(salt: str) -> bytes:
    b = salt.encode("utf-8")
    if len(b) != 8:
        raise ValueError(f"salt must be 8 bytes, got {len(b)}: {salt!r}")
    return b


def des_encrypt_raw(key: str, data: bytes) -> bytes:
    k = _key_bytes(key)
    if len(data) % 8:
        data = data + b"\x00" * (8 - len(data) % 8)
    if not data:
        return b""
    c = Cipher(TripleDES(k * 3), modes.ECB())
    e = c.encryptor()
    return e.update(data) + e.finalize()


def encrypt(value, salt: str) -> str:
    """value 为 str 时原样；其它类型按 JSON 序列化（对齐 SDK 的 smStringify）。"""
    if isinstance(value, str):
        plain = value
    else:
        plain = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    if plain == "":
        return ""
    return base64.b64encode(des_encrypt_raw(salt, plain.encode("utf-8"))).decode("ascii")


if __name__ == "__main__":
    print(encrypt("hello", "e1024477"), "expect jB5WOwO8t+8=")
    print(encrypt("abcdefgh", "e1024477"), "expect EAuZGMv2JAQ=")
    print(encrypt("abcdefghi", "e1024477"), "expect EAuZGMv2JAQ13gJ6nA0NnQ==")
    print(encrypt(123, "e1024477"))
