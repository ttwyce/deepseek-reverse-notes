"""诊断：手动 initSMCaptcha 后 widget 为何测不到尺寸。
打印 wrapper 自身与父链的 computed style / rect，以及 SDK 脚本加载状态。"""
import json
import os

from playwright.sync_api import sync_playwright

OUT = os.path.join("work", "sm")
os.makedirs(OUT, exist_ok=True)

PROBE = r"""() => {
  const out = {t: Date.now()};
  out.scripts = [...document.querySelectorAll('script[src]')].map(s => s.src).filter(s => s.includes('fengkong') || s.includes('captcha'));
  out.globals = {SMCaptcha: typeof window.SMCaptcha, initSMCaptcha: typeof window.initSMCaptcha,
                 _smConf: typeof window._smConf, _smReadyFuncs: typeof window._smReadyFuncs};
  out.result = window.__capResult || null;
  const w = document.querySelector('[id$="_shumei_captcha_wrapper"]');
  if (!w) { out.wrapper = null; return out; }
  const chain = [];
  let n = w, d = 0;
  while (n && n !== document.documentElement && d < 6) {
    const r = n.getBoundingClientRect();
    const cs = getComputedStyle(n);
    chain.push({tag: n.tagName, id: (n.id||'').slice(0,26), cls: (n.className||'').toString().slice(0,40),
                rect: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
                display: cs.display, visibility: cs.visibility, opacity: cs.opacity,
                position: cs.position, overflow: cs.overflow});
    n = n.parentElement; d++;
  }
  out.chain = chain;
  out.wrapperHTML = w.outerHTML.slice(0, 700);
  const iw = w.querySelector('[class*="img_wrapper"]');
  if (iw) {
    const r = iw.getBoundingClientRect();
    out.imgWrapper = {rect: [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)],
                      html: iw.outerHTML.slice(0, 600)};
  }
  out.mycapRect = (() => { const m = document.getElementById('mycap'); if(!m) return null;
    const r = m.getBoundingClientRect(); return [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]; })();
  return out;
}"""


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                                  user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                              "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"))
        page = ctx.new_page()

        def on_register(route):
            try:
                resp = route.fetch()
                body = resp.text()
                new = body.replace('"riskLevel":"PASS"', '"riskLevel":"REJECT"')
                print("[route] 改写", new[:150])
                route.fulfill(response=resp, body=new)
            except Exception as exc:
                print("[route] fail", exc)
                route.continue_()

        page.route("**/ca/v1/register*", on_register)
        page.on("console", lambda m: print("[console]", m.type, m.text[:200]) if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: print("[pageerror]", str(e)[:300]))

        page.goto("https://chat.deepseek.com/sign_in", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1200)

        page.evaluate("""() => {
            const d = document.createElement('div');
            d.id = 'mycap';
            d.style.cssText = 'position:fixed;left:20px;top:20px;z-index:999999;width:340px;height:260px;background:#fff;';
            document.body.appendChild(d);
            window.__capResult = null;
            window.initSMCaptcha({
                organization: 'P9usCUBauxft8eAmUXaZ', appendTo: 'mycap', lang: 'zh-cn',
                mode: 'spatial_select', maskBindClose: false,
                onSuccess: (r) => { window.__capResult = {ok: true, r}; },
                onError: (e) => { window.__capResult = {ok: false, e}; },
                onClose: () => { window.__capResult = window.__capResult || {closed: true}; }
            }, (ret) => { window.__capResult = {cb: ret}; });
        }""")

        for i in range(16):
            page.wait_for_timeout(900)
            info = page.evaluate(PROBE)
            print(f"\n===== tick {i} =====")
            print(json.dumps(info, ensure_ascii=False)[:2600])
            if info.get("chain"):
                top = info["chain"][0]["rect"]
                if top[2] >= 50 and top[3] >= 50:
                    print(">>> 尺寸达标，可以点击")
                    page.screenshot(path=os.path.join(OUT, "diag_ok.png"))
                    break
        page.screenshot(path=os.path.join(OUT, "diag_end.png"))
        with open(os.path.join(OUT, "diag.json"), "w", encoding="utf-8") as fh:
            json.dump(page.evaluate(PROBE), fh, ensure_ascii=False, indent=1)
        browser.close()


if __name__ == "__main__":
    main()
