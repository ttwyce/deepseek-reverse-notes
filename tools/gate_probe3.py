"""WAF 会话续接实验：首次 429 会下发 HWWAFSESID，带上该 cookie 再请求是否放行。"""
import sys

import requests

PROXIES = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
H = {
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
    print(f"---- {tag}: HTTP {r.status_code} block={r.headers.get('Block-Event-Id')} len={len(r.content)}")
    print("     body:", r.text[:200].replace("\n", " "))
    print()


def main():
    s = requests.Session()
    s.headers.update(H)

    r1 = s.get("https://chat.deepseek.com/", proxies=PROXIES, timeout=30, allow_redirects=False)
    brief("1 首次 GET /", r1)
    print("   cookies:", s.cookies.get_dict())

    r2 = s.get("https://chat.deepseek.com/", proxies=PROXIES, timeout=30, allow_redirects=False)
    brief("2 带 cookie 再 GET /", r2)
    print("   cookies:", s.cookies.get_dict())

    r3 = s.get("https://chat.deepseek.com/api/v0/client/settings", proxies=PROXIES, timeout=30)
    brief("3 带 cookie GET /api/v0/client/settings", r3)

    r4 = s.post("https://chat.deepseek.com/api/v0/users/login", json={}, proxies=PROXIES, timeout=30)
    brief("4 带 cookie POST /api/v0/users/login", r4)

    # 5 换个 UA 试浏览器 UA
    s.headers["User-Agent"] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
    r5 = s.get("https://chat.deepseek.com/", proxies=PROXIES, timeout=30, allow_redirects=False)
    brief("5 浏览器 UA GET /", r5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
