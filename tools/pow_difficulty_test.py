"""验证 difficulty 语义：上界是 difficulty 还是 2^difficulty。"""
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
print("challenge:", r.status_code, r.text[:600])
c = r.json()["data"]["biz_data"]["guest_challenge"]
print("parsed:", json.dumps(c, ensure_ascii=False))

tgt = bytes.fromhex(c["challenge"])
salt, exp, diff = c["salt"], c["expire_at"], c["difficulty"]
print(f"salt={salt} exp={exp} diff={diff} tgtlen={len(tgt)}")

# 假设1：base = salt_expireAt_
base = f"{salt}_{exp}_".encode()
limit = 1 << min(diff + 4, 26)
print(f"brute force 0..{limit}")
found = None
for n in range(limit):
    if hashlib.sha3_256(base + str(n).encode()).digest() == tgt:
        found = n
        break
print("found(base=salt_exp_)", found)

# 假设2：base = salt_ （无 expire_at）
if found is None:
    base2 = f"{salt}_".encode()
    for n in range(limit):
        if hashlib.sha3_256(base2 + str(n).encode()).digest() == tgt:
            found = n
            print("found(base=salt_)", n)
            break

# 假设3：base = challenge 原文 + nonce（hex 字符串）
if found is None:
    b3 = c["challenge"].encode()
    for n in range(limit):
        if hashlib.sha3_256(b3 + str(n).encode()).digest() == tgt:
            found = n
            print("found(base=challengehex)", n)
            break
print("final", found)
