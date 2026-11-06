"""用真实 challenge 反推 PoW 的 sponge 模型。

native (librscrypto.so 0x19bc0) 的流程疑似「非标准 sponge」：
  base 先 absorb 并置换，再追加 nonce 十进制串 + 0x06 域 + 0x80 尾位，再置换，取前 32 字节与 challenge 全等比较。
标准 hashlib.sha3_256(base+nonce) 已验证不命中，故这里穷举若干模型变体。
"""

# ---------- Keccak-f[1600] ----------
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


def rol(v, n):
    n %= 64
    return ((v << n) | (v >> (64 - n))) & M64


def keccak_f(a, rounds=24):
    """a: list[25] of int64 lanes, lane index = x + 5*y"""
    for rnd in range(rounds):
        # theta
        c = [a[x] ^ a[x + 5] ^ a[x + 10] ^ a[x + 15] ^ a[x + 20] for x in range(5)]
        d = [c[(x - 1) % 5] ^ rol(c[(x + 1) % 5], 1) for x in range(5)]
        for x in range(5):
            for y in range(5):
                a[x + 5 * y] ^= d[x]
        # rho + pi
        b = [0] * 25
        for x in range(5):
            for y in range(5):
                b[y + 5 * ((2 * x + 3 * y) % 5)] = rol(a[x + 5 * y], ROT[x][y])
        # chi
        for x in range(5):
            for y in range(5):
                a[x + 5 * y] = b[x + 5 * y] ^ ((~b[(x + 1) % 5 + 5 * y]) & b[(x + 2) % 5 + 5 * y] & M64)
        # iota
        a[0] ^= RC[rnd]
    return a


def state_to_bytes(a):
    out = bytearray(200)
    for i, lane in enumerate(a):
        out[i * 8:i * 8 + 8] = lane.to_bytes(8, "little")
    return out


def bytes_to_state(buf):
    a = [0] * 25
    for i in range(25):
        a[i] = int.from_bytes(buf[i * 8:i * 8 + 8], "little")
    return a


def xor_into(a, data, offset=0):
    for i, byte in enumerate(data):
        idx = offset + i
        lane = idx // 8
        sh = (idx % 8) * 8
        a[lane] ^= byte << sh
    return a


def absorb_block(a, block136):
    xor_into(a, block136)
    return keccak_f(a)


# ---------- 模型变体 ----------
def m_std_sha3(base, nonce):
    import hashlib
    return hashlib.sha3_256(base + str(nonce).encode()).digest()


def m_std_keccak_pad01(base, nonce):
    """原始 Keccak（padding 0x01）"""
    data = base + str(nonce).encode()
    a = [0] * 25
    padded = bytearray(data)
    padlen = 136 - (len(data) % 136)
    if padlen == 0:
        padlen = 136
    padded += b"\x01" + b"\x00" * (padlen - 2) + b"\x80" if padlen > 1 else b"\x81"
    for i in range(0, len(padded), 136):
        absorb_block(a, padded[i:i + 136])
    return state_to_bytes(a)[:32]


def m_two_stage(base, nonce):
    """base 单独 absorb+置换，再 nonce+0x06+0x80 置换"""
    a = [0] * 25
    xor_into(a, base)
    keccak_f(a)
    ns = str(nonce).encode()
    xor_into(a, ns)
    xor_into(a, b"\x06", len(ns))
    xor_into(a, b"\x80", 135)
    keccak_f(a)
    return state_to_bytes(a)[:32]


def m_two_stage_basepadded(base, nonce):
    """base 补零到 136 后 absorb+置换"""
    a = [0] * 25
    xor_into(a, base)
    keccak_f(a)
    ns = str(nonce).encode()
    xor_into(a, ns)
    xor_into(a, b"\x06", len(ns))
    xor_into(a, b"\x80", 135)
    keccak_f(a)
    return state_to_bytes(a)[:32]


def m_single_block(base, nonce):
    """base+nonce 放同一块，0x06+0x80 单次置换"""
    a = [0] * 25
    data = base + str(nonce).encode()
    xor_into(a, data)
    xor_into(a, b"\x06", len(data))
    xor_into(a, b"\x80", 135)
    keccak_f(a)
    return state_to_bytes(a)[:32]


def m_std_sha3_hexnonce(base, nonce):
    import hashlib
    return hashlib.sha3_256(base + format(nonce, "x").encode()).digest()


MODELS = {
    "std_sha3": m_std_sha3,
    "std_sha3_hexnonce": m_std_sha3_hexnonce,
    "keccak_pad01": m_std_keccak_pad01,
    "two_stage": m_two_stage,
    "single_block": m_single_block,
}


def main():
    challenge = "f6115aeb908268aa454296193bf67fca08fba355d32c01de6c3eae3cfe24080c"
    salt = "408c87d6f327d6257cbc"
    expire_at = 1792936998058
    difficulty = 20
    target = bytes.fromhex(challenge)

    bases = {
        "salt_exp_ms_": f"{salt}_{expire_at}_",
        "salt_exp_s_": f"{salt}_{expire_at // 1000}_",
        "salt_": f"{salt}_",
        "salt": salt,
        "salt_exp_ms": f"{salt}_{expire_at}",
    }

    for bname, base in bases.items():
        for mname, fn in MODELS.items():
            for nonce in range(max(difficulty * 100, 2000)):
                if fn(base.encode(), nonce) == target:
                    print(f"*** HIT base={bname} model={mname} nonce={nonce}")
                    return
        print(f"[{bname}] 未命中")

    # 同时验证 self-test：标准 sha3 是否能复现自己构造的 target
    import hashlib
    t2 = hashlib.sha3_256(b"abc_123_7").digest()
    assert m_std_sha3(b"abc_123_", 7) == t2
    print("自检 OK（std_sha3 实现正确）")


if __name__ == "__main__":
    main()
