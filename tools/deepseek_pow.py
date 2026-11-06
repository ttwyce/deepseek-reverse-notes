"""DeepSeek PoW (DeepSeekHashV1) 完整实现 + guest challenge 求解 + 邮箱验证码申请。

算法（由 librscrypto.so 0x19bc0 反汇编 + 实测确认）：
  base   = salt + "_" + expire_at + "_"
  data   = base + str(nonce)
  digest = Keccak-f[1600](padding=0x06..0x80, rate=136, rounds=23, start=RC[1])[:32]
  条件   = digest == bytes.fromhex(challenge)
  nonce  = 0 .. difficulty-1 中第一个命中的值
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
import hashlib
import json
import sys

import requests

API = "https://chat.deepseek.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

HEADERS = {
    "User-Agent": UA,
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Origin": API,
    "Referer": API + "/",
    "x-client-platform": "android",
    "x-client-version": "2.7.1",
    "x-client-bundle-id": "com.deepseek.chat",
    "x-client-locale": "zh_CN",
    "x-client-timezone-offset": "28800",
    "x-device-model": "Pixel 6",
}

# ---------------- Keccak（23 轮，跳过 RC[0]） ----------------
RC = [
    0x0000000000000001, 0x0000000000008082, 0x800000000000808A, 0x8000000080008000,
    0x000000000000808B, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
    0x000000000000008A, 0x0000000000000088, 0x0000000080008009, 0x000000008000000A,
    0x000000008000808B, 0x800000000000008B, 0x8000000000008089, 0x8000000000008003,
    0x8000000000008002, 0x8000000000000080, 0x000000000000800A, 0x800000008000000A,
    0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008,
]
ROT = [
    [0, 36, 3, 41, 18], [1, 44, 10, 45, 2], [62, 6, 43, 15, 61],
    [28, 55, 25, 21, 56], [27, 20, 39, 8, 14],
]
M64 = (1 << 64) - 1


def _rol(v, n):
    n %= 64
    return ((v << n) | (v >> (64 - n))) & M64


def _keccak_f(a, rounds=23, start=1):
    for rnd in range(start, start + rounds):
        c = [a[x] ^ a[x + 5] ^ a[x + 10] ^ a[x + 15] ^ a[x + 20] for x in range(5)]
        d = [c[(x - 1) % 5] ^ _rol(c[(x + 1) % 5], 1) for x in range(5)]
        for x in range(5):
            for y in range(5):
                a[x + 5 * y] ^= d[x]
        b = [0] * 25
        for x in range(5):
            for y in range(5):
                b[y + 5 * ((2 * x + 3 * y) % 5)] = _rol(a[x + 5 * y], ROT[x][y])
        for x in range(5):
            for y in range(5):
                a[x + 5 * y] = b[x + 5 * y] ^ ((~b[(x + 1) % 5 + 5 * y]) & b[(x + 2) % 5 + 5 * y] & M64)
        a[0] ^= RC[rnd % 24]
    return a


def deepseek_hash(data: bytes) -> bytes:
    a = [0] * 25
    padded = bytearray(data)
    padlen = 136 - (len(data) % 136)
    if padlen == 1:
        padded += b"\x86"
    else:
        padded += b"\x06" + b"\x00" * (padlen - 2) + b"\x80"
    for i in range(0, len(padded), 136):
        blk = padded[i:i + 136]
        for j, byte in enumerate(blk):
            a[j // 8] ^= byte << ((j % 8) * 8)
        _keccak_f(a)
    out = bytearray(200)
    for i, lane in enumerate(a):
        out[i * 8:i * 8 + 8] = lane.to_bytes(8, "little")
    return bytes(out[:32])


def solve(challenge_hex: str, salt: str, expire_at: int, difficulty: int):
    target = bytes.fromhex(challenge_hex)
    base = f"{salt}_{expire_at}_".encode()
    for nonce in range(max(difficulty, 1)):
        if deepseek_hash(base + str(nonce).encode()) == target:
            return nonce
    return None


# ---------------- 业务流程 ----------------
def get_guest_challenge(target_path):
    r = requests.post(
        API + "/api/v0/users/create_guest_challenge",
        headers=HEADERS, json={"target_path": target_path}, timeout=20,
    )
    return r.json()


def build_pow_header(gc: dict) -> str:
    nonce = solve(gc["challenge"], gc["salt"], gc["expire_at"], gc["difficulty"])
    if nonce is None:
        raise RuntimeError("PoW 求解失败")
    solution = {
        "algorithm": gc["algorithm"],
        "challenge": gc["challenge"],
        "salt": gc["salt"],
        "signature": gc["signature"],
        "answer": nonce,
        "target_path": gc["target_path"],
    }
    return base64.b64encode(json.dumps(solution, separators=(",", ":")).encode()).decode(), nonce


def main():
    email = sys.argv[1] if len(sys.argv) > 1 else _cred("DS_EMAIL")
    tp = "/api/v0/users/create_email_verification_code"

    # 1) 自检：确认模型可复现已知样本
    print("[1] 自检已知样本 …")
    known = {
        "challenge": "f6115aeb908268aa454296193bf67fca08fba355d32c01de6c3eae3cfe24080c",
        "salt": "408c87d6f327d6257cbc",
        "expire_at": 1792936998058,
        "difficulty": 20,
    }
    n = solve(known["challenge"], known["salt"], known["expire_at"], known["difficulty"])
    print(f"    nonce = {n}  ({'OK' if n == 14 else '异常'})")

    # 2) 取新 challenge 并求解
    print("[2] 请求 guest challenge …")
    resp = get_guest_challenge(tp)
    print("   ", json.dumps(resp, ensure_ascii=False)[:400])
    gc = resp["data"]["biz_data"]["guest_challenge"]
    header, nonce = build_pow_header(gc)
    print(f"    nonce = {nonce}")
    print(f"    X-DS-Guest-Pow-Response = {header[:80]}…")

    # 3) 带 PoW 头申请邮箱验证码
    print("[3] 申请邮箱验证码 …")
    h = dict(HEADERS)
    h["X-DS-Guest-Pow-Response"] = header
    body = {"email": email, "locale": "zh_CN", "device_id": "a" * 32}
    r = requests.post(API + "/api/v0/users/create_email_verification_code",
                      headers=h, json=body, timeout=20)
    print("    HTTP", r.status_code)
    print("   ", r.text[:600])


if __name__ == "__main__":
    main()
