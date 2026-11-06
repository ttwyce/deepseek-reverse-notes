# -*- coding: utf-8 -*-
"""一次完成：真实浏览器取 smid/device_id → 立刻纯协议登录。

验证假设：biz_code 11 RISK_DEVICE_DETECTED 是否因缺少数美 smid 所致。
浏览器只用于生成设备指纹，登录本身仍走纯 HTTP。
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
from playwright.sync_api import sync_playwright

sys.path.insert(0, r"F:\dshh\deepseeka\tools")
from deepseek_client import BASE, UA  # noqa: E402

EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")


def harvest() -> dict:
    """开一个全新浏览器上下文，抓 smid / device_id / cookies。"""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=[
            "--disable-blink-features=AutomationControlled", "--no-first-run"])
        ctx = browser.new_context(viewport={"width": 1366, "height": 900},
                                  locale="zh-CN", timezone_id="Asia/Shanghai")
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
        page = ctx.new_page()
        page.goto("https://chat.deepseek.com/sign_in",
                  wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(6000)
        data = page.evaluate("""() => ({
            deviceId: localStorage.getItem('deepseek-device-id:chat'),
            smidLocal: localStorage.getItem('smidV2'),
            thumb: localStorage.getItem('.thumbcache_6b2e5483f9d858d7c661c5e276b6a6ae'),
            did: localStorage.getItem('__ds_remote_feature_did'),
        })""")
        cookies = {c["name"]: c["value"] for c in ctx.cookies()}
        browser.close()
    data["cookies"] = cookies
    return data


def login(dev: dict, tag: str, os_name: str, with_cred: bool) -> dict:
    s = requests.Session()
    s.trust_env = False
    for name in ("smidV2", "ds_session_id", "HWWAFSESTIME", "HWWAFSESID",
                 ".thumbcache_6b2e5483f9d858d7c661c5e276b6a6ae"):
        if dev["cookies"].get(name):
            s.cookies.set(name, dev["cookies"][name], domain="chat.deepseek.com")
    device_id = dev["deviceId"]
    headers = {
        "User-Agent": UA, "Accept": "*/*", "Accept-Language": "zh-CN,zh;q=0.9",
        "Content-Type": "application/json", "Origin": BASE,
        "Referer": BASE + "/sign_in",
        "x-client-bundle-id": "com.deepseek.chat", "x-client-platform": "web",
        "x-client-version": "2.7.0", "x-client-locale": "zh_CN",
        "x-client-timezone-offset": "28800",
        "x-device-id": device_id, "x-device-model": "",
    }
    body = {"email": EMAIL, "password": PASSWORD,
            "device_id": device_id, "os": os_name}
    if with_cred:
        body["credential_id"] = ""
    r = s.post(BASE + "/api/v0/users/login", headers=headers,
               data=json.dumps(body).encode(), timeout=30)
    try:
        j = r.json()
    except ValueError:
        j = {"raw": r.text[:200]}
    print(f"{tag:46s} HTTP {r.status_code} {json.dumps(j, ensure_ascii=False)[:300]}")
    return j


def main() -> None:
    dev = harvest()
    print("device_id   =", dev["deviceId"])
    print("smidV2      =", (dev["smidLocal"] or "")[:60])
    print("cookie smid =", (dev["cookies"].get("smidV2") or "")[:60])
    print("did         =", dev["did"])
    print("cookies     =", list(dev["cookies"].keys()))
    json.dump(dev, open(r"F:\dshh\deepseeka\work\pw_device.json", "w",
                        encoding="utf-8"), ensure_ascii=False, indent=2)

    login(dev, "E 全新设备 os=web+cred", "web", True)
    time.sleep(8)
    login(dev, "F 全新设备 os=android", "android", False)


if __name__ == "__main__":
    main()
