# -*- coding: utf-8 -*-
"""真实 Chrome + 持久化 profile 打开 /sign_up，手动渲染 Turnstile 看能否拿到 token。

用法:
    python tools/pw_chrome_ts.py [--headless]
"""
import sys
import time
import pathlib

from playwright.sync_api import sync_playwright

WORK = pathlib.Path(r"F:\dshh\deepseeka\work")
PROFILE = WORK / "chrome_profile"
PROXY = "http://127.0.0.1:7890"
SITEKEY = "0x4AAAAAAA1jQEh8YFk064tz"

HEADLESS = "--headless" in sys.argv

RENDER_JS = """
(sitekey) => {
  if (typeof turnstile !== 'object') return {ok:false, err:'no turnstile obj'};
  let host = document.getElementById('my-ts');
  if (!host) {
    host = document.createElement('div');
    host.id = 'my-ts';
    host.style.cssText = 'position:fixed;left:10px;top:10px;z-index:999999;background:#fff';
    document.body.appendChild(host);
  }
  window.__tok = null;
  window.__err = null;
  try {
    const id = turnstile.render('#my-ts', {
      sitekey: sitekey,
      callback: (t) => { window.__tok = t; },
      'error-callback': (e) => { window.__err = 'errcb:' + e; return true; },
      'timeout-callback': () => { window.__err = 'timeout'; },
    });
    return {ok:true, id: id};
  } catch (e) {
    return {ok:false, err:String(e)};
  }
}
"""

STATE_JS = """
() => ({
  tok: window.__tok ? window.__tok.length : 0,
  err: window.__err,
  ifrAll: document.querySelectorAll('iframe').length,
  ifrHost: document.querySelectorAll('#my-ts iframe').length,
  html: (document.getElementById('my-ts') || {}).innerHTML ? 'yes' : 'no',
})
"""


def main() -> None:
    PROFILE.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE),
            channel="chrome",
            headless=HEADLESS,
            proxy={"server": PROXY},
            locale="en-US",
            timezone_id="Asia/Tokyo",
            viewport={"width": 1280, "height": 900},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://chat.deepseek.com/sign_up", wait_until="domcontentloaded", timeout=60000)
        time.sleep(9)

        print("title :", page.title())
        meta = page.evaluate(
            "() => { const g = n => { const e = document.querySelector('meta[name=\"'+n+'\"]');"
            " return e ? e.content : null; }; return {ip:g('ip'), region:g('region')}; }"
        )
        print("meta  :", meta)
        print("ua    :", page.evaluate("() => navigator.userAgent"))
        print("webdriver:", page.evaluate("() => navigator.webdriver"))
        print("inputs:", page.evaluate("() => document.querySelectorAll('input').length"))

        print("render:", page.evaluate(RENDER_JS, SITEKEY))

        done = False
        for i in range(60):
            time.sleep(1)
            st = page.evaluate(STATE_JS)
            if i % 5 == 0:
                print(f"  [{i:2d}s]", st)
            if st["tok"] or st["err"]:
                print("FINAL:", st)
                done = True
                break
        if not done:
            print("FINAL: timeout-no-token")

        page.screenshot(path=str(WORK / "pw_chrome_ts.png"))
        ctx.close()


if __name__ == "__main__":
    main()
