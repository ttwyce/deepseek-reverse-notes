"""穷举 PoW base 拼接变体，命中即报告。"""
import hashlib
import json
import uuid

from curl_cffi import requests as creq

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
TARGET = "/api/v0/users/create_email_verification_code"
h = {
    "User-Agent": UA,
    "Accept": "*/*",
    "Content-Type": "application/json",
    "Origin": "https://chat.deepseek.com",
    "Referer": "https://chat.deepseek.com/",
    "x-client-platform": "android",
    "x-client-version": "2.7.1",
    "x-client-bundle-id": "com.deepseek.chat",
    "x-client-locale": "zh_CN",
    "x-client-timezone-offset": "28800",
    "x-device-model": "Pixel 6",
    "x-ds-trace-id": str(uuid.uuid4()),
}

s = creq.Session(impersonate="chrome")
r = s.post(
    "https://chat.deepseek.com/api/v0/users/create_guest_challenge",
    data=json.dumps({"target_path": TARGET}),
    headers=h,
    timeout=30,
)
c = r.json()["data"]["biz_data"]["guest_challenge"]
ch, salt = c["challenge"], c["salt"]
exp, expa, diff = c["expire_at"], c["expire_after"], c["difficulty"]
tgt = bytes.fromhex(ch)
print(json.dumps(c, ensure_ascii=False))

cands = {
    "salt_exp_": f"{salt}_{exp}_",
    "salt_exp": f"{salt}_{exp}",
    "salt_expAfter_": f"{salt}_{expa}_",
    "salt_diff_": f"{salt}_{diff}_",
    "salt_": f"{salt}_",
    "salt": salt,
    "exp_salt_": f"{exp}_{salt}_",
    "salt_exp_diff_": f"{salt}_{exp}_{diff}_",
    "salt_exp_expAfter_": f"{salt}_{exp}_{expa}_",
    "challenge_exp_": f"{ch}_{exp}_",
    "salt_exp_nounder": f"{salt}{exp}",
    "salt_exp_after_nounder": f"{salt}{expa}",
}

LIMIT = 300_000
for name, base in cands.items():
    b = base.encode()
    hit = None
    for n in range(LIMIT):
        if hashlib.sha3_256(b + str(n).encode()).digest() == tgt:
            hit = ("dec", n)
            break
    if hit is None:
        for n in range(min(LIMIT, 100_000)):
            if hashlib.sha3_256(b + format(n, "x").encode()).digest() == tgt:
                hit = ("hex", n)
                break
    print(f"{name:24s} -> {hit}")
    if hit:
        break
