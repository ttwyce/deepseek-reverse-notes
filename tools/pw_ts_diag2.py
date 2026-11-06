# -*- coding: utf-8 -*-
"""诊断 Turnstile 为何不出 iframe，并检查页面是否加载 hCaptcha。"""
import json
import time
import pathlib

from playwright.sync_api import sync_playwright

WORK = pathlib.Path(r"F:\dshh\deepseeka\work")
PROFILE = WORK / "chrome_profile"
PROXY = "http://127.0.0.1:7890"

DIAG_JS = r"""
() => {
  const out = {};
  out.hasTS = typeof window.turnstile;
  try { out.tsKeys = Object.keys(window.turnstile || {}); } catch(e) { out.tsKeys = 'err'; }
  try { out.renderSrc = String(window.turnstile.render).slice(0, 240); } catch(e) { out.renderSrc = 'err'; }
  out.scripts = [...document.scripts].map(s => s.src).filter(Boolean);
  out.hosts = document.querySelectorAll('[id^="cf-chl-widget"]').length;
  const my = document.getElementById('my-ts');
  out.hostHtmlLen = my ? my.innerHTML.length : -1;
  out.hostHtml = my ? my.innerHTML.slice(0, 400) : '';
  out.iframes = [...document.querySelectorAll('iframe')].map(f => (f.src || '').slice(0, 100));
  out.hasHcaptcha = typeof window.hcaptcha;
  out.hcapScripts = [...document.scripts].map(s => s.src).filter(s => s && s.includes('hcaptcha'));
  out.cfOverlay = (() => {
    const o = document.getElementById('cf-overlay');
    return o ? {display: getComputedStyle(o).display, kids: o.children.length} : null;
  })();
  return out;
}
"""

RENDER_JS = r"""
(sitekey) => {
  let host = document.getElementById('my-ts');
  if (!host) {
    host = document.createElement('div');
    host.id = 'my-ts';
    host.style.cssText = 'position:fixed;left:10px;top:10px;z-index:999999;background:#fff;width:320px;height:80px';
    document.body.appendChild(host);
  }
  window.__tok = null; window.__err = null; window.__wid = null;
  try {
    window.__wid = turnstile.render('#my-ts', {
      sitekey: sitekey,
      callback: t => { window.__tok = t; },
      'error-callback': e => { window.__err = 'errcb:' + e; return true; },
      'timeout-callback': () => { window.__err = 'timeout'; },
    });
    return {ok:true, id: window.__wid};
  } catch (e) { return {ok:false, err:String(e)}; }
}
"""


def main() -> None:
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(PROFILE), channel="chrome", headless=False,
            proxy={"server": PROXY}, locale="en-US", timezone_id="Asia/Tokyo",
            viewport={"width": 1280, "height": 900},
            args=["--disable-blink-features=AutomationControlled", "--no-first-run"],
        )
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://chat.deepseek.com/sign_up", wait_until="domcontentloaded", timeout=60000)
        time.sleep(9)

        d1 = page.evaluate(DIAG_JS)
        print("=== BEFORE RENDER ===")
        print(json.dumps(d1, ensure_ascii=False, indent=1)[:2500])

        print("render:", page.evaluate(RENDER_JS, "0x4AAAAAAA1jQEh8YFk064tz"))
        for i in range(25):
            time.sleep(1)
            st = page.evaluate(
                "() => ({tok: window.__tok ? window.__tok.length : 0, err: window.__err,"
                " wid: window.__wid,"
                " resp: (() => { try { return String((turnstile.getResponse(window.__wid)||'')).length; } catch(e){ return 'e'; } })(),"
                " exist: document.querySelectorAll('[id^=cf-chl-widget]').length,"
                " ifr: document.querySelectorAll('iframe').length})"
            )
            if i % 5 == 0:
                print(f"  [{i:2d}s]", st)
            if st["tok"] or st["err"]:
                print("FINAL:", st)
                break
        else:
            print("FINAL: still no token")

        d2 = page.evaluate(DIAG_JS)
        print("=== AFTER RENDER ===")
        print(json.dumps({k: v for k, v in d2.items() if k != "scripts"}, ensure_ascii=False, indent=1)[:2500])
        print("script hosts:", [s.split('/')[2] for s in d2["scripts"] if "//" in s])
        page.screenshot(path=str(WORK / "pw_ts_diag2.png"))
        ctx.close()


if __name__ == "__main__":
    main()
