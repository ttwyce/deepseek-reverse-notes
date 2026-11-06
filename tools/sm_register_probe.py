"""直接请求数美 register，观察不同指纹/参数下的 riskLevel 与返回结构。

不带任何设备指纹、无 cookie、无 smid 时，数美通常返回 REJECT 并要求验证，
此时 detail 里会带完整题目（bg/k/l/order/rid），正是求解器需要解析的部分。
"""
import json
import random
import string
import time

import requests

ORG = "P9usCUBauxft8eAmUXaZ"


def uuid(n=19):
    return str(int(time.time() * 1000)) + "".join(random.choices(string.ascii_letters + string.digits, k=12))


def call(url, **kw):
    r = requests.get(url, timeout=20, **kw)
    txt = r.text
    print(f"\n--- {url[:120]} -> {r.status_code} {len(txt)}B")
    print(txt[:1500])
    return txt


def main():
    base = "https://captcha1.fengkongcloud.cn/ca/v1/register"
    # 1) 最简：只有 organization + model + appId
    call(base, params={"organization": ORG, "lang": "zh-cn", "model": "spatial_select",
                       "appId": "default", "rversion": "1.0.4", "captchaUuid": uuid(),
                       "callback": "sm_123"})
    # 2) 加 sdkver
    call(base, params={"organization": ORG, "lang": "zh-cn", "model": "spatial_select",
                       "appId": "default", "rversion": "1.0.4", "sdkver": "1.0.4",
                       "captchaUuid": uuid(), "callback": "sm_124"})
    # 3) 默认 model（不给 model）
    call(base, params={"organization": ORG, "lang": "zh-cn", "appId": "default",
                       "rversion": "1.0.4", "captchaUuid": uuid(), "callback": "sm_125"})
    # 4) 带常见 web 参数
    call(base, params={"organization": ORG, "lang": "zh-cn", "model": "spatial_select",
                       "appId": "default", "rversion": "1.0.4", "sdkver": "1.0.4",
                       "channel": "default", "captchaUuid": uuid(),
                       "act.os": "web", "callback": "sm_126"},
         headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
                  "Referer": "https://chat.deepseek.com/",
                  "Origin": "https://chat.deepseek.com"})


if __name__ == "__main__":
    main()
