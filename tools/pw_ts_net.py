# -*- coding: utf-8 -*-
"""监听 challenges.cloudflare.com 的网络往来 + console（含 CSP 违规），再 render Turnstile。"""
import json
import time
import pathlib

from playwright.sync_api import sync_playwright

WORK = pathlib.Path(r"F:\dshh\deepseeka\work")
PROFILE = WORK / "chrome_profile"
PROXY = "http://127.0.0.1:7890"
SITEKEY = "0x4AAAAAAA1jQEh8YFk064tz"

net = []
cons = []

RENDER_JS = r"""
(sitekey) => {
  let host = document.getElementById('my-ts');
  if (!host) {
    host = document.createElement('div');
    host.id = 'my-ts';
    host.style.cssText = 'position:fixed;left:10px;top:10px;z-index:999999;background:#fff;width:320px;height:90px';
    document.body.appendChild(host);
  }
  window.__tok = null; window.__err = null;
  const id = turnstile.render('#my-ts', {
    sitekey: sitekey,
    callback: t => { window.__tok = t; },
    'error-callback': e => { window.__err = 'errcb:' + e; return true; },
    'timeout-callback': () => { window.__err = 'timeout'; },
  });
  return {ok:true, id};
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

        page.on("console", lambda m: cons.append(f"[{m.type}] {m.text[:300]}"))
        page.on("requestfailed", lambda r: net.append(
            {"kind": "FAILED", "url": r.url[:120], "err": str(r.failure)[:160]}))
        page.on("response", lambda r: net.append(
            {"kind": "RESP", "status": r.status, "url": r.url[:120]}))

        page.goto("https://chat.deepseek.com/sign_up", wait_until="domcontentloaded", timeout=60000)
        time.sleep(8)

        csp = page.evaluate(
            "() => { const m = document.querySelector('meta[http-equiv=\"Content-Security-Policy\"]');"
            " return m ? m.content : null; }"
        )
        print("meta CSP:", csp)

        net.clear()
        print("render:", page.evaluate(RENDER_JS, SITEKEY))
        for i in range(20):
            time.sleep(1)
            st = page.evaluate(
                "() => ({tok: window.__tok ? window.__tok.length : 0, err: window.__err,"
                " ifr: document.querySelectorAll('iframe').length})")
            if i % 5 == 0:
                print(f"  [{i:2d}s]", st)
            if st["tok"] or st["err"]:
                print("FINAL:", st)
                break

        print("\n=== NET (challenges.cloudflare.com 相关) ===")
        seen = set()
        for n in net:
            if "cloudflare" in n["url"] or n["kind"] == "FAILED":
                key = (n["kind"], n.get("status"), n["url"])
                if key in seen:
                    continue
                seen.add(key)
                print(json.dumps(n, ensure_ascii=False))
        print("\n=== total net events:", len(net))
        fails = [n for n in net if n["kind"] == "FAILED"]
        print("failed count:", len(fails))
        for f in fails[:10]:
            print("  ", f["url"], "|", f["err"])

        print("\n=== CONSOLE (最后 25 条) ===")
        for c in cons[-25:]:
            print(" ", c)

        ctx.close()


if __name__ == "__main__":
    main()
