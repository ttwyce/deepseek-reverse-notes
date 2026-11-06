# -*- coding: utf-8 -*-
"""验证代理对 chat.deepseek.com 是否真的生效：对比直连 / 经 7890 时服务端看到的 IP。

判据：页面 <meta name="ip"> 与 <meta name="region">（服务端按真实连接 IP 渲染）。

用法：python tools\\geo_field_probe2.py
"""
from __future__ import annotations

import re
import sys

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
PROXY = "http://127.0.0.1:7890"

RE_IP = re.compile(r'<meta name="ip" content="([^"]*)"')
RE_REGION = re.compile(r'<meta name="region" content="([^"]*)"')


def probe(label: str, proxies: dict | None) -> None:
    s = requests.Session()
    s.trust_env = False
    try:
        r = s.get("https://chat.deepseek.com/sign_up",
                  headers={"user-agent": UA, "accept": "text/html"},
                  proxies=proxies, timeout=25)
        ip = RE_IP.search(r.text)
        rg = RE_REGION.search(r.text)
        print(f"[{label:12s}] HTTP {r.status_code}  meta.ip={ip.group(1) if ip else '-':16s} meta.region={rg.group(1) if rg else '-'}")
        # 顺带看出口（第三方）
        r2 = s.get("https://api.ipify.org", proxies=proxies, timeout=20)
        print(f"{'':14s}  api.ipify.org 出口 = {r2.text.strip()}")
    except Exception as e:
        print(f"[{label:12s}] FAIL {type(e).__name__}: {e}")


def main() -> None:
    print("=== 对照实验：谁看到了哪个 IP ===\n")
    probe("direct", None)
    print()
    probe("via-7890", {"http": PROXY, "https": PROXY})
    print()
    # 再确认代理本身是否活着、以及是否对国内域名也直连
    s = requests.Session()
    s.trust_env = False
    try:
        r = s.get("https://api.ipify.org", proxies={"https": PROXY}, timeout=20)
        print("[proxy-live] api.ipify.org 经代理 =", r.text.strip())
    except Exception as e:
        print("[proxy-live] FAIL", e)


if __name__ == "__main__":
    main()
