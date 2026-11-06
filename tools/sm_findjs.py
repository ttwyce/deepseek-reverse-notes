"""找出 chat.deepseek.com 前端 JS bundle，并搜索数美（shumei/SMSdk/initSMCaptcha）调用点。"""
import re
import sys

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")

BASE = "https://chat.deepseek.com"


def main():
    s = requests.Session()
    s.headers["User-Agent"] = UA
    r = s.get(BASE + "/sign_in", timeout=20)
    print("sign_in:", r.status_code, len(r.text))
    srcs = re.findall(r'<script[^>]+src="([^"]+)"', r.text)
    print("scripts:", len(srcs))
    for x in srcs:
        print("  ", x)

    hits = []
    for src in srcs:
        url = src if src.startswith("http") else BASE + ("" if src.startswith("/") else "/") + src
        try:
            rr = s.get(url, timeout=30)
        except Exception as e:
            print("  ERR", url, type(e).__name__)
            continue
        t = rr.text
        print(f"  {len(t):>9} B  {url}")
        for kw in ("initSMCaptcha", "shumei", "SMSdk", "_smConf", "captcha", "smcp"):
            n = t.count(kw)
            if n:
                hits.append((url, kw, n))
    print("\n=== keyword hits ===")
    for url, kw, n in hits:
        print(f"  {kw:15s} x{n:<4d} {url}")


if __name__ == "__main__":
    sys.exit(main())
