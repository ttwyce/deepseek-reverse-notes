# -*- coding: utf-8 -*-
"""等数美 deviceprofile 完成后再取 device_id，然后纯协议登录。

数美 SDK 流程：本地指纹 -> POST {apiHost}/deviceprofile/v4 -> 服务端 smid
-> 写 localStorage .thumbcache_<md5(organization)>。只有该值被服务端登记后，
登录 body 的 device_id 才被认作可信设备。
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
from enc_login_test import base_headers, encrypt_body  # noqa: E402

BASE = "https://chat.deepseek.com"
EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")
WORK = r"F:\dshh\deepseeka\work"
CHROME = (r"F:\dshh\deepseeka\tools\pw-browsers\chromium-1248"
          r"\chrome-win64\chrome.exe")


def grab_device_id(wait_profile: bool = True, max_wait: int = 25):
    from playwright.sync_api import sync_playwright

    profile_done = {"ok": False, "detail": None}

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, executable_path=CHROME,
                              args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(
            locale="zh-CN", timezone_id="Asia/Shanghai",
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/156.0.0.0 Safari/537.36"))
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = ctx.new_page()

        def on_resp(r):
            if "deviceprofile" in r.url or "portal101" in r.url:
                try:
                    profile_done["detail"] = r.text()[:400]
                except Exception:  # noqa: BLE001
                    profile_done["detail"] = "<binary>"
                profile_done["ok"] = True
                print(f"[deviceprofile] {r.status} {r.url}")

        page.on("response", on_resp)
        page.goto("https://chat.deepseek.com/", wait_until="domcontentloaded")

        if wait_profile:
            t0 = time.time()
            while not profile_done["ok"] and time.time() - t0 < max_wait:
                page.wait_for_timeout(500)
            # 再等 SDK 写回 localStorage
            page.wait_for_timeout(3000)

        st = page.evaluate("""() => {
            const o = {};
            for (let i = 0; i < localStorage.length; i++) {
                const k = localStorage.key(i); o[k] = localStorage.getItem(k);
            }
            return o;
        }""")
        cookies = {c["name"]: c["value"] for c in ctx.cookies()}
        b.close()

    thumb = ""
    uuid = ""
    for k, v in st.items():
        if k.startswith(".thumbcache_"):
            thumb = v
        if k == "deepseek-device-id:chat":
            uuid = v
    return thumb, uuid, st, cookies, profile_done


def main() -> None:
    dev, uuid, st, cookies, prof = grab_device_id()
    print("\nprofile_done:", prof["ok"], "detail:", (prof["detail"] or "")[:200])
    print("device_id len:", len(dev))
    print("device_id:", dev)
    print("deepseek-device-id:", uuid)
    print("smidV2:", st.get("smidV2"))
    with open(WORK + r"\devid_probe.json", "w", encoding="utf-8") as f:
        json.dump({"device_id": dev, "uuid": uuid, "storage": st,
                   "cookies": cookies}, f, ensure_ascii=False, indent=2)

    if not dev:
        print("未取到 device_id")
        return

    sess = requests.Session()
    sess.trust_env = False
    body = {"email": EMAIL, "mobile": "", "area_code": "", "password": PASSWORD,
            "device_id": dev, "os": "web", "credential_id": ""}
    plain = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode()
    key_hdr, ct = encrypt_body(plain)
    h = base_headers(dev)
    h["x-request-encryption-key"] = key_hdr
    r = sess.post(BASE + "/api/v0/users/login", data=ct, headers=h, timeout=30)
    print("\n== login ==", r.status_code, r.text[:300])


if __name__ == "__main__":
    main()
