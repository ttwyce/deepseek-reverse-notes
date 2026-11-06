# -*- coding: utf-8 -*-
"""探测：Android 端请求头组合哪一组能通过 WAF。

对照 4 组，全部请求 GET /api/v0/users/current：
  A  okhttp UA + 完整 Android 头        （真实 App 形态）
  B  Chrome UA + 完整 Android 头
  C  okhttp UA + 无 x-client-* 头
  D  curl_cffi(chrome 指纹) + okhttp UA + Android 头
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from token_store import TokenStore  # noqa: E402

BASE = "https://chat.deepseek.com"
URL = BASE + "/api/v0/users/current"

UA_OKHTTP = "okhttp/4.12.0"
UA_CHROME = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36")

ANDROID_HEADERS = {
    "x-client-platform": "android",
    "x-client-version": "2.7.1",
    "x-client-locale": "zh_CN",
    "x-client-bundle-id": "com.deepseek.chat",
    "x-client-timezone-offset": "28800",
    "x-device-model": "SM-G991B",
}


def base(token: str) -> dict:
    return {
        "accept": "*/*",
        "authorization": f"Bearer {token}",
        "accept-encoding": "gzip",
    }


def show(tag: str, r) -> None:
    body = r.text[:220].replace("\n", " ")
    print(f"[{tag}] {r.status_code}  {body}")


def main() -> None:
    info = TokenStore().load()
    token = info["token"]
    print(f"token len={len(token)}  device_id={str(info.get('device_id'))[:24]}...")

    cases = [
        ("A okhttp+android", UA_OKHTTP, ANDROID_HEADERS),
        ("B chrome+android", UA_CHROME, ANDROID_HEADERS),
        ("C okhttp only", UA_OKHTTP, {}),
        ("D chrome only", UA_CHROME, {}),
    ]

    s = requests.Session()
    s.trust_env = False
    for tag, ua, extra in cases:
        h = base(token)
        h["user-agent"] = ua
        h.update(extra)
        try:
            r = s.get(URL, headers=h, timeout=20)
            show(tag, r)
        except Exception as e:  # noqa: BLE001
            print(f"[{tag}] EXC {type(e).__name__}: {e}")

    # D 组：curl_cffi 模拟 Chrome TLS 指纹
    try:
        from curl_cffi import requests as creq
        h = base(token)
        h["user-agent"] = UA_OKHTTP
        h.update(ANDROID_HEADERS)
        r = creq.get(URL, headers=h, impersonate="chrome", timeout=20)
        show("E curl_cffi+okhttp+android", r)
        h2 = base(token)
        h2["user-agent"] = UA_CHROME
        h2.update(ANDROID_HEADERS)
        r2 = creq.get(URL, headers=h2, impersonate="chrome", timeout=20)
        show("F curl_cffi+chrome+android", r2)
    except Exception as e:  # noqa: BLE001
        print(f"[curl_cffi] EXC {type(e).__name__}: {e}")


if __name__ == "__main__":
    main()
