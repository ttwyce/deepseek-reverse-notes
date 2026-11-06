# -*- coding: utf-8 -*-
"""Hook crypto.subtle.encrypt，抓取网页端加密前的明文 JSON 与 key||iv。

eR 实现：subtle.encrypt({name:"AES-CBC",iv}, aesKey, plaintextBytes)
         subtle.encrypt({name:"RSA-OAEP"}, rsaKey, key||iv)
=> hook 后可直接看到明文。
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

HOOK = r"""
(() => {
  const orig = SubtleCrypto.prototype.encrypt;
  window.__encLog = [];
  SubtleCrypto.prototype.encrypt = function(alg, key, data) {
    try {
      const name = alg && alg.name;
      if (name === 'AES-CBC' && data) {
        const bytes = new Uint8Array(data);
        const txt = new TextDecoder().decode(bytes);
        window.__encLog.push({type: 'AES-CBC', len: bytes.length, plain: txt});
      } else if (name === 'RSA-OAEP' && data) {
        const b = new Uint8Array(data);
        window.__encLog.push({type: 'RSA-OAEP', len: b.length,
                              hex: Array.from(b).map(x=>x.toString(16).padStart(2,'0')).join('')});
      }
    } catch (e) {}
    return orig.apply(this, arguments);
  };
})();
"""


def main() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=[
            "--disable-blink-features=AutomationControlled", "--no-first-run"])
        ctx = browser.new_context(viewport={"width": 1366, "height": 900},
                                  locale="zh-CN", timezone_id="Asia/Shanghai")
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});")
        ctx.add_init_script(HOOK)
        page = ctx.new_page()

        def on_resp(resp):
            if "/api/v0/users/login" in resp.url:
                try:
                    print("RESP", resp.status, resp.text()[:300])
                except Exception:  # noqa: BLE001
                    pass

        page.on("response", on_resp)
        page.goto("https://chat.deepseek.com/sign_in",
                  wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(5000)
        page.evaluate("""() => {
            for (const el of document.querySelectorAll('.ds-button__content')) {
                if ((el.textContent||'').trim() === '密码登录') {
                    (el.closest('button') || el.parentElement).click(); return;
                }
            }
        }""")
        page.wait_for_timeout(2500)
        page.fill("input[placeholder*='手机号/邮箱']", EMAIL, timeout=10000)
        page.fill("input[type=password]", PASSWORD, timeout=10000)
        page.evaluate("""() => {
            for (const el of document.querySelectorAll('.ds-button__content')) {
                if ((el.textContent||'').trim() === '登录') {
                    (el.closest('button') || el.parentElement).click(); return true;
                }
            }
            return false;
        }""")
        page.wait_for_timeout(12000)

        logs = page.evaluate("() => window.__encLog || []")
        print("\n=== captured encryption inputs ===")
        for item in logs:
            print(json.dumps(item, ensure_ascii=False)[:800])

        with open(WORK + r"\pw_enc_inputs.json", "w", encoding="utf-8") as fh:
            json.dump(logs, fh, ensure_ascii=False, indent=2)
        browser.close()


if __name__ == "__main__":
    main()
