"""验证 hif 令牌是否为 chat.deepseek.com 的 WAF 放行凭证。

对照实验：
  A. www.deepseek.com 首页（代理 IP 是否整体被封）
  B. chat.deepseek.com/api/v0/client/settings 不带 hif 头
  C. 先取 hif 令牌，再带 x-hif-dliq / x-hif-leim 请求同一接口
"""
import json
import sys

import requests

PROXIES = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
BASE_H = {
    "x-client-platform": "android",
    "x-client-version": "2.7.1",
    "x-client-bundle-id": "com.deepseek.chat",
    "x-client-locale": "zh_CN",
    "x-client-timezone-offset": "28800",
    "x-device-model": "Pixel 6",
    "User-Agent": "okhttp/4.12.0",
    "Accept": "*/*",
    "Referer": "https://chat.deepseek.com",
}


def brief(tag, r):
    print(f"---- {tag}: HTTP {r.status_code}  ct={r.headers.get('Content-Type')}  block={r.headers.get('Block-Event-Id')}")
    print("     ", r.text[:400].replace("\n", " "))
    print()


def fetch_hif():
    out = {}
    for name, host in (("dliq", "hif-dliq"), ("leim", "hif-leim")):
        r = requests.get(f"https://{host}.deepseek.com/query", headers=BASE_H, proxies=PROXIES, timeout=30)
        tok = None
        if r.status_code == 200:
            try:
                tok = r.json()["data"]["biz_data"]["value"]
            except Exception:
                tok = None
        out[name] = tok
        print(f"hif {name}: HTTP {r.status_code} ttl={r.headers.get('x-hif-ttl')} token={'OK' if tok else 'NONE'}")
    return out


def main():
    # A 对照
    try:
        r = requests.get("https://www.deepseek.com/", headers=BASE_H, proxies=PROXIES, timeout=30, allow_redirects=False)
        brief("A www.deepseek.com", r)
    except Exception as e:
        print("A 异常:", e)

    # B 不带 hif
    try:
        r = requests.get("https://chat.deepseek.com/api/v0/client/settings", headers=BASE_H, proxies=PROXIES, timeout=30)
        brief("B chat/api 无 hif", r)
    except Exception as e:
        print("B 异常:", e)

    # C 带 hif
    toks = fetch_hif()
    h = dict(BASE_H)
    if toks.get("dliq"):
        h["x-hif-dliq"] = toks["dliq"]
    if toks.get("leim"):
        h["x-hif-leim"] = toks["leim"]
    try:
        r = requests.get("https://chat.deepseek.com/api/v0/client/settings", headers=h, proxies=PROXIES, timeout=30)
        brief("C chat/api 带 hif", r)
    except Exception as e:
        print("C 异常:", e)

    # D 带 hif 打 login（密文 body 稍后处理，先看 WAF 是否放行）
    try:
        r = requests.post("https://chat.deepseek.com/api/v0/users/login", headers=h, json={}, proxies=PROXIES, timeout=30)
        brief("D chat/login 带 hif（空 body）", r)
    except Exception as e:
        print("D 异常:", e)
    return 0


if __name__ == "__main__":
    sys.exit(main())
