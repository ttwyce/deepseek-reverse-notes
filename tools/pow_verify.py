"""验证 guest challenge 的 PoW base 格式（用真实服务端下发的 challenge）。

假设（来自 nfb.smali:431-646 + me0.smali）：
  base      = salt + "_" + expire_at + "_"   (expire_at 为服务端原始值，13 位毫秒)
  challenge = 64 hex -> 32 字节目标
  nonce     = 十进制字符串追加到 base 之后
  digest    = sha3_256(base + str(nonce))  必须 == challenge 字节
"""
import hashlib
import json
import sys
import time

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


def get_guest_challenge(target_path):
    r = requests.post(
        API + "/api/v0/users/create_guest_challenge",
        headers=HEADERS,
        json={"target_path": target_path},
        timeout=20,
    )
    return r.status_code, r.text


def try_bases(gc, limit=2_000_000):
    salt = gc["salt"]
    exp = gc["expire_at"]
    target = bytes.fromhex(gc["challenge"])
    cands = {
        "salt_exp_ms_": f"{salt}_{exp}_",
        "salt_exp_s_": f"{salt}_{exp // 1000}_",
        "salt_": f"{salt}_",
        "salt_exp_ms": f"{salt}_{exp}",
        "salt_exp_s": f"{salt}_{exp // 1000}",
        "exp_ms_salt_": f"{exp}_{salt}_",
        "exp_s_salt_": f"{exp // 1000}_{salt}_",
        "salt_expAfter_": f"{salt}_{gc['expire_after']}_",
        "salt_diff_": f"{salt}_{gc['difficulty']}_",
    }
    hits = {}
    for name, base in cands.items():
        b = base.encode()
        for nonce in range(limit):
            if hashlib.sha3_256(b + str(nonce).encode()).digest() == target:
                hits[name] = nonce
                break
    return hits


def main():
    tp = sys.argv[1] if len(sys.argv) > 1 else "/api/v0/users/create_email_verification_code"
    code, text = get_guest_challenge(tp)
    print("HTTP", code)
    print(text[:1200])
    try:
        data = json.loads(text)["data"]["biz_data"]["guest_challenge"]
    except Exception as e:
        print("parse fail:", e)
        return
    print("\nchallenge 字段：")
    for k, v in data.items():
        print(f"  {k} = {v}")

    # 先用小范围确认
    t0 = time.time()
    hits = try_bases(data, limit=200_000)
    print(f"\n搜索 20 万/变体，耗时 {time.time() - t0:.1f}s")
    print("命中：", hits if hits else "无")


if __name__ == "__main__":
    main()
