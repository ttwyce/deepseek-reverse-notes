# -*- coding: utf-8 -*-
"""用真实浏览器生成的 smidV2 + device_id 做纯协议登录。

浏览器访问一次网页会生成：
  cookie/localStorage: smidV2 = <数美 smid>
  localStorage: deepseek-device-id:chat = <UUID v4>
服务端 biz_code 11 RISK_DEVICE_DETECTED 极可能就是因为缺少 smid。
"""
from __future__ import annotations
# --- credentials: 从环境变量或本地 local_config.py 读取（local_config 不入库）---
import os as _os


def _cred(key, default=""):
    v = _os.environ.get(key)
    if v:
        return v
    try:
        from local_config import CFG  # type: ignore
        return CFG.get(key, default)
    except Exception:
        return default



import json
import sys
import time

import requests

sys.path.insert(0, r"F:\dshh\deepseeka\tools")
from deepseek_client import BASE, UA  # noqa: E402

EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")

# 来自 tools/web_playwright_login.py 一次真实访问
SMID = "20261025222435182421674356c11dfb738010223673c80077d00a2bbd1d510"
DEVICE_ID = "dd456180-85a8-48a2-a627-5af925f24e9b"
DS_SESSION = "b6a8197d59ee4887aeea293e4ecf1eb3"
HWWAF_TIME = "1792938272526"
HWWAF_SID = "1031521317ec90dccef1"


def build_headers(device_id: str) -> dict[str, str]:
    return {
        "User-Agent": UA,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Content-Type": "application/json",
        "Origin": BASE,
        "Referer": BASE + "/sign_in",
        "x-client-bundle-id": "com.deepseek.chat",
        "x-client-platform": "web",
        "x-client-version": "2.7.0",
        "x-client-locale": "zh_CN",
        "x-client-timezone-offset": "28800",
        "x-device-id": device_id,
        "x-device-model": "",
    }


def attempt(tag: str, use_cookie: bool, os_name: str, with_cred: bool,
            device_id: str = DEVICE_ID) -> dict:
    s = requests.Session()
    s.trust_env = False
    if use_cookie:
        s.cookies.set("smidV2", SMID, domain="chat.deepseek.com")
        s.cookies.set("ds_session_id", DS_SESSION, domain="chat.deepseek.com")
        s.cookies.set("HWWAFSESTIME", HWWAF_TIME, domain="chat.deepseek.com")
        s.cookies.set("HWWAFSESID", HWWAF_SID, domain="chat.deepseek.com")
    body = {"email": EMAIL, "password": PASSWORD,
            "device_id": device_id, "os": os_name}
    if with_cred:
        body["credential_id"] = ""
    r = s.post(BASE + "/api/v0/users/login", headers=build_headers(device_id),
               data=json.dumps(body).encode(), timeout=30)
    try:
        j = r.json()
    except ValueError:
        j = {"raw": r.text[:200]}
    print(f"{tag:52s} HTTP {r.status_code} {json.dumps(j, ensure_ascii=False)[:260]}")
    return j


def main() -> None:
    attempt("A cookie(smid)+os=web+cred", True, "web", True)
    time.sleep(6)
    attempt("B cookie(smid)+os=android", True, "android", False)
    time.sleep(6)
    attempt("C no-cookie+os=web+cred (对照)", False, "web", True)
    time.sleep(6)
    attempt("D cookie+os=web+随机device_id", True, "web", True,
            device_id="2ba67119-1fdf-4f16-ae43-2a25e913ea62")


if __name__ == "__main__":
    main()
