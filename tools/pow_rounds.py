"""验证 native 的 Keccak 轮数。

反汇编显示 `mov w1, #0x17`（23）作为 keccak 轮数传入，且函数内有
`cmp x1,#0x19; b.hs` → 超过 24 报错。若实际只跑 23 轮，则输出不是标准 SHA3-256，
这正好解释为什么 hashlib.sha3_256 无法复现。
"""
import hashlib

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


def keccak_f(a, rounds, start=0):
    for rnd in range(start, start + rounds):
        c = [a[x] ^ a[x + 5] ^ a[x + 10] ^ a[x + 15] ^ a[x + 20] for x in range(5)]
        d = [c[(x - 1) % 5] ^ rol(c[(x + 1) % 5], 1) for x in range(5)]
        for x in range(5):
            for y in range(5):
                a[x + 5 * y] ^= d[x]
        b = [0] * 25
        for x in range(5):
            for y in range(5):
                b[y + 5 * ((2 * x + 3 * y) % 5)] = rol(a[x + 5 * y], ROT[x][y])
        for x in range(5):
            for y in range(5):
                a[x + 5 * y] = b[x + 5 * y] ^ ((~b[(x + 1) % 5 + 5 * y]) & b[(x + 2) % 5 + 5 * y] & M64)
        a[0] ^= RC[rnd % 24]
    return a


def digest(data, rounds=24, start=0):
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
        keccak_f(a, rounds, start)
    out = bytearray(200)
    for i, lane in enumerate(a):
        out[i * 8:i * 8 + 8] = lane.to_bytes(8, "little")
    return bytes(out[:32])


def selftest():
    assert digest(b"", 24) == hashlib.sha3_256(b"").digest(), "24 轮实现自检失败"
    assert digest(b"abc", 24) == hashlib.sha3_256(b"abc").digest(), "24 轮实现自检失败(abc)"
    print("24 轮实现自检 OK")


GC = {
    "challenge": "f6115aeb908268aa454296193bf67fca08fba355d32c01de6c3eae3cfe24080c",
    "salt": "408c87d6f327d6257cbc",
    "expire_at": 1792936998058,
    "expire_after": 300000,
    "difficulty": 20,
    "target_path": "/v0/users/create_email_verification_code",
}


def main():
    selftest()
    target = bytes.fromhex(GC["challenge"])
    salt = GC["salt"]
    bases = {
        "salt_exp_ms_": f"{salt}_{GC['expire_at']}_",
        "salt_exp_s_": f"{salt}_{GC['expire_at'] // 1000}_",
        "salt_ea_": f"{salt}_{GC['expire_after']}_",
        "salt_diff_": f"{salt}_{GC['difficulty']}_",
        "salt_0_": f"{salt}_0_",
    }
    rounds_set = [(23, 0), (23, 1), (24, 0), (22, 0), (22, 1)]
    for bname, base in bases.items():
        for rounds, start in rounds_set:
            for n in range(4096):
                if digest((base + str(n)).encode(), rounds, start) == target:
                    print(f"*** HIT base={bname} rounds={rounds} start={start} nonce={n}")
                    return
        print(f"[{bname}] 未命中")
    print("全部未命中")


if __name__ == "__main__":
    main()
