"""DeepSeek 网关探测 —— 会话建立 / WAF cookie / hif 令牌通道。

用法： .venv\\Scripts\\python.exe tools\\gate_probe.py
"""
import sys

import requests

PROXIES = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
UA_APP = "okhttp/4.12.0"

TARGETS = [
    ("首页", "GET", "https://chat.deepseek.com/", None),
    ("hif-dliq", "GET", "https://hif-dliq.deepseek.com/query", None),
    ("hif-leim", "GET", "https://hif-leim.deepseek.com/query", None),
]


def show(tag, r):
    print(f"---- {tag}: HTTP {r.status_code}")
    for k in ("Content-Type", "Server", "Block-Event-Id", "x-hif-ttl", "Content-Length"):
        if k in r.headers:
            print(f"     {k} = {r.headers[k]}")
    sc = r.headers.get("Set-Cookie")
    if sc:
        print("     Set-Cookie =", sc[:300])
    body = r.text
    print("     body[:600] =", body[:600].replace("\n", " "))
    print()


def main():
    s = requests.Session()
    s.headers.update({
        "x-client-platform": "android",
        "x-client-version": "2.7.1",
        "x-client-bundle-id": "com.deepseek.chat",
        "x-client-locale": "zh_CN",
        "x-client-timezone-offset": "28800",
        "x-device-model": "Pixel 6",
        "User-Agent": UA_APP,
        "Accept": "*/*",
    })
    for tag, m, url, _ in TARGETS:
        try:
            r = s.request(m, url, proxies=PROXIES, timeout=30, allow_redirects=False)
        except Exception as e:
            print(f"---- {tag}: 异常 {type(e).__name__}: {e}\n")
            continue
        show(tag, r)
    print("== session cookies:", s.cookies.get_dict())
    return 0


if __name__ == "__main__":
    sys.exit(main())
