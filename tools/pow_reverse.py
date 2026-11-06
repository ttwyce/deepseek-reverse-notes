"""反推服务端 guest challenge 的 base 构造。

思路：challenge / signature 都是 64 hex（32 字节），可能是 sha3_256 / sha256 的某种组合。
若 challenge = sha3_256(base + str(nonce))，那么 base 一定在若干候选里。
本脚本同时比对 signature，尝试用 signature 揭示 base 的拼接格式。
"""
import hashlib
import itertools

GC = {
    "algorithm": "DeepSeekHashV1",
    "challenge": "f6115aeb908268aa454296193bf67fca08fba355d32c01de6c3eae3cfe24080c",
    "salt": "408c87d6f327d6257cbc",
    "signature": "e2233fd0e28cfeb5154169cbcb0a7f5dc67611c856ee9504237157deee4a9f6f",
    "difficulty": 20,
    "expire_at": 1792936998058,
    "expire_after": 300000,
    "target_path": "/v0/users/create_email_verification_code",
}

HASHES = {
    "sha3_256": lambda b: hashlib.sha3_256(b).digest(),
    "sha256": lambda b: hashlib.sha256(b).digest(),
    "blake2s": lambda b: hashlib.blake2s(b).digest(),
    "shake128_32": lambda b: hashlib.shake_128(b).digest(32),
    "shake256_32": lambda b: hashlib.shake_256(b).digest(32),
}

CH = bytes.fromhex(GC["challenge"])
SIG = bytes.fromhex(GC["signature"])

salt = GC["salt"]
vals = {
    "salt": salt,
    "exp_ms": str(GC["expire_at"]),
    "exp_s": str(GC["expire_at"] // 1000),
    "ea": str(GC["expire_after"]),
    "diff": str(GC["difficulty"]),
    "tp": GC["target_path"],
    "alg": GC["algorithm"],
    "ch": GC["challenge"],
    "sig": GC["signature"],
}

# 1) 检查 signature 是否 = hash(某组合)
print("=== 用 signature 反推 base ===")
found_sig = False
for hname, hf in HASHES.items():
    for k, v in vals.items():
        if hf(v.encode()) == SIG:
            print(f"*** signature = {hname}({k})")
            found_sig = True
    for r in (2, 3):
        for combo in itertools.permutations(vals.keys(), r):
            for sep in ("_", "", ":", "|"):
                s = sep.join(vals[c] for c in combo)
                if hf(s.encode()) == SIG:
                    print(f"*** signature = {hname}({'+'.join(combo)} sep={sep!r})")
                    found_sig = True
if not found_sig:
    print("signature 未匹配任何单/双/三字段哈希")

# 2) 检查 challenge 是否 = hash(某组合 + 小整数)
print("\n=== 用 challenge 反推 base（nonce 0..1023）===")
found_ch = False
cands = {}
for k, v in vals.items():
    cands[k] = v
    cands[f"{k}_"] = v + "_"
for r in (2, 3):
    for combo in itertools.permutations(vals.keys(), r):
        for sep in ("_", "", ":", "|"):
            cands["+".join(combo) + f"|{sep}"] = sep.join(vals[c] for c in combo)
            cands["+".join(combo) + f"|{sep}|trail"] = sep.join(vals[c] for c in combo) + sep

print(f"候选 base：{len(cands)}")
for hname, hf in HASHES.items():
    for name, base in cands.items():
        b = base.encode()
        if len(b) > 135:
            continue
        for n in range(1024):
            if hf(b + str(n).encode()) == CH:
                print(f"*** challenge = {hname}({name} + {n})  base={base!r}")
                found_ch = True
                break
if not found_ch:
    print("challenge 未匹配")

# 3) 检查 challenge 是否直接是 hash(base)（nonce 参与别处）
print("\n=== challenge = hash(base) 无 nonce ===")
for hname, hf in HASHES.items():
    for name, base in cands.items():
        if hf(base.encode()) == CH:
            print(f"*** challenge = {hname}({name})")
            found_ch = True
if not found_ch:
    print("无")
