# -*- coding: utf-8 -*-
"""同一时刻对比：登录 body 里的 device_id vs localStorage 各候选值。

目标：确定 device_id 到底等于哪个存储值 / 哪个接口返回。
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

from playwright.sync_api import sync_playwright

EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")
WORK = r"F:\dshh\deepseeka\work"
CHROME = (r"F:\dshh\deepseeka\tools\pw-browsers\chromium-1248"
          r"\chrome-win64\chrome.exe")

plain_box: list[str] = []
resp_box: list[dict] = []


def main() -> None:
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, executable_path=CHROME,
                              args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(
            locale="zh-CN", timezone_id="Asia/Shanghai",
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/156.0.0.0 Safari/537.36"))
        ctx.add_init_script("""
            Object.defineProperty(navigator,'webdriver',{get:()=>undefined});
            (() => {
              const orig = SubtleCrypto.prototype.encrypt;
              SubtleCrypto.prototype.encrypt = async function(alg, key, data) {
                try {
                  if (alg && alg.name === 'AES-CBC' && data) {
                    const txt = new TextDecoder().decode(new Uint8Array(data));
                    window.__lastPlain = txt;
                  }
                } catch (e) {}
                return orig.apply(this, arguments);
              };
            })();
        """)
        page = ctx.new_page()

        def on_resp(r):
            if "portal101" in r.url or "deviceprofile" in r.url:
                try:
                    resp_box.append({"url": r.url, "body": r.text()[:500]})
                except Exception:  # noqa: BLE001
                    pass

        page.on("response", on_resp)
        page.goto("https://chat.deepseek.com/sign_in", wait_until="domcontentloaded")
        page.wait_for_timeout(6000)

        # 登录前快照
        before = page.evaluate("""() => {
            const o = {};
            for (let i = 0; i < localStorage.length; i++) {
                const k = localStorage.key(i); o[k] = localStorage.getItem(k);
            }
            return o;
        }""")
        print("=== deviceprofile 响应 ===")
        for r in resp_box:
            print(" ", r["body"][:300])

        page.evaluate("""() => {
            for (const el of document.querySelectorAll('.ds-button__content')) {
                if (el.textContent.trim() === '密码登录') {
                    (el.closest('button') || el.parentElement).click();
                    return true;
                }
            }
            return false;
        }""")
        page.wait_for_timeout(1200)
        page.fill("input[placeholder*='手机号/邮箱']", EMAIL)
        page.fill("input[type=password]", PASSWORD)
        page.wait_for_timeout(300)
        page.evaluate("""() => {
            for (const el of document.querySelectorAll('.ds-button__content')) {
                if (el.textContent.trim() === '登录') {
                    (el.closest('button') || el.parentElement).click();
                    return true;
                }
            }
            return false;
        }""")
        page.wait_for_timeout(6000)

        plain = page.evaluate("() => window.__lastPlain || null")
        after = page.evaluate("""() => {
            const o = {};
            for (let i = 0; i < localStorage.length; i++) {
                const k = localStorage.key(i); o[k] = localStorage.getItem(k);
            }
            return o;
        }""")
        b.close()

    print("\n=== 登录 body 明文 ===")
    print(plain)
    dev = ""
    if plain:
        try:
            dev = json.loads(plain).get("device_id", "")
        except Exception:  # noqa: BLE001
            pass
    print("\nbody.device_id:", dev, "len=", len(dev))

    print("\n=== 候选比对 ===")
    for label, snap in (("before", before), ("after", after)):
        for k, v in snap.items():
            mark = "  <== 相同" if v == dev else ""
            if k.startswith(".thumbcache_") or "device" in k or "smid" in k.lower():
                print(f"[{label}] {k} = {v[:100]}{mark}")
    for r in resp_box:
        print("deviceprofile resp:", r["body"][:250])
        if dev and dev in r["body"]:
            print("  <== body.device_id 出现在 deviceprofile 响应中")

    with open(WORK + r"\devid_compare.json", "w", encoding="utf-8") as f:
        json.dump({"plain": plain, "device_id": dev, "before": before,
                   "after": after, "profiles": resp_box}, f,
                  ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
