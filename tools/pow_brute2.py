"""在 sha3_256(base + str(nonce)) == challenge 的模型下，穷举 base 的组合变体。

模型依据：librscrypto.so 0x19bc0 实为标准 SHA3-256 单块 absorb
  - state(200B) @ sp+0x30 清零
  - base memcpy 到 msg 缓冲 sp+0xf8，长度存 msg[135]
  - nonce 十进制串追加到 msg[base_len..]
  - padding: msg[cur] ^= 0x06, msg[135] ^= 0x80
  - keccak_f(state, 24) 后取前 32 字节与 challenge 全等比较
"""
import hashlib
import itertools
import json

CH = {
    "algorithm": "DeepSeekHashV1",
    "challenge": "f6115aeb908268aa454296193bf67fca08fba355d32c01de6c3eae3cfe24080c",
    "salt": "408c87d6f327d6257cbc",
    "signature": "e2233fd0e28cfeb5154169cbcb0a7f5dc67611c856ee9504237157deee4a9f6f",
    "difficulty": 20,
    "expire_at": 1792936998058,
    "expire_after": 300000,
    "target_path": "/v0/users/create_email_verification_code",
}


def build_candidates():
    salt = CH["salt"]
    exp_ms = str(CH["expire_at"])
    exp_s = str(CH["expire_at"] // 1000)
    ea = str(CH["expire_after"])
    diff = str(CH["difficulty"])
    sig = CH["signature"]
    tp = CH["target_path"]
    alg = CH["algorithm"]
    ch = CH["challenge"]

    parts = {
        "salt": salt, "exp_ms": exp_ms, "exp_s": exp_s,
        "ea": ea, "diff": diff, "sig": sig, "tp": tp,
        "alg": alg, "ch": ch,
        "tp_noapi": tp.replace("/api", "", 1),
    }

    out = {}

    # 1) 两段/三段用 _ 连接的高概率组合
    seqs = [
        ["salt", "exp_ms"], ["salt", "exp_s"],
        ["salt", "exp_ms", "ea"], ["salt", "exp_ms", "diff"],
        ["salt", "exp_s", "ea"],
        ["salt", "ea"], ["salt", "diff"],
        ["salt", "exp_ms", "sig"], ["salt", "exp_ms", "tp"],
        ["salt", "exp_ms", "tp_noapi"],
        ["salt", "exp_ms", "alg"], ["salt", "ch"],
        ["exp_ms", "salt"], ["ch", "salt"],
        ["salt"], ["exp_ms"],
        ["alg", "salt", "exp_ms"], ["tp", "salt", "exp_ms"],
    ]
    seps = ["_", "", ":", "|", "."]
    for seq in seqs:
        for sep in seps:
            for trailing in (True, False):
                base = sep.join(parts[k] for k in seq)
                if trailing:
                    base += sep
                out[f"{'+'.join(seq)}|sep={sep!r}|trail={trailing}"] = base

    # 2) JSON 形式
    out["json_all"] = json.dumps(CH, separators=(",", ":"), sort_keys=True)
    out["json_salt_exp"] = json.dumps({"salt": salt, "expire_at": CH["expire_at"]},
                                     separators=(",", ":"))

    return out


def main():
    target = bytes.fromhex(CH["challenge"])
    cands = build_candidates()
    print(f"候选 base 数：{len(cands)}")

    checked = 0
    for name, base in cands.items():
        b = base.encode()
        if len(b) > 135:
            continue
        for nonce in range(0, 4096):
            checked += 1
            if hashlib.sha3_256(b + str(nonce).encode()).digest() == target:
                print(f"*** HIT  base={name!r}\n    value={base!r}\n    nonce={nonce}")
                return
    print(f"未命中（共试 {checked} 次）")


if __name__ == "__main__":
    main()
