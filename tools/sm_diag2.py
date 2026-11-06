"""精简诊断：只看 DOM 尺寸 / CSS 表 / 图片状态，不打印 _config 大对象。"""
import json
import os

from playwright.sync_api import sync_playwright

OUT = os.path.join("work", "sm")

PROBE = r"""() => {
  const w = document.querySelector('[id$="_shumei_captcha_wrapper"]');
  const sheets = [...document.styleSheets].map(s => s.href).filter(Boolean).filter(h => h.includes('fengkong'));
  const out = {sheets};
  if (!w) { out.wrapper = null; return out; }
  const r = w.getBoundingClientRect();
  const cs = getComputedStyle(w);
  out.wrapper = {rect: [Math.round(r.width), Math.round(r.height)], display: cs.display, visibility: cs.visibility,
                 overflow: cs.overflow, position: cs.position};
  const kids = [...w.children].map(c => {
    const cr = c.getBoundingClientRect(); const ccs = getComputedStyle(c);
    return {cls: (c.className||'').toString().slice(0,50), wh: [Math.round(cr.width), Math.round(cr.height)],
            display: ccs.display};
  });
  out.kids = kids;
  const imgs = [...w.querySelectorAll('img')].map(i => ({cls:(i.className||'').slice(0,40), src:(i.src||'').split('/').pop().slice(0,40),
                    natural: [i.naturalWidth, i.naturalHeight], complete: i.complete,
                    wh: [Math.round(i.getBoundingClientRect().width), Math.round(i.getBoundingClientRect().height)]}));
  out.imgs = imgs;
  out.htmlLen = w.innerHTML.length;
  return out;
}"""


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                                  user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                              "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"))
        page = ctx.new_page()
        page.on("pageerror", lambda e: print("[pageerror]", str(e)[:200]))
        page.on("console", lambda m: print("[console]", m.type, m.text[:160]) if m.type == "error" else None)
        page.on("requestfailed", lambda r: print("[reqfail]", r.url[:100], r.failure) if "fengkong" in r.url else None)
        page.goto("https://chat.deepseek.com/sign_in", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(800)
        page.evaluate("""() => {
            const d = document.createElement('div');
            d.id = 'mycap';
            d.style.cssText = 'position:fixed;left:20px;top:20px;z-index:999999;width:340px;';
            document.body.appendChild(d);
            window.__capResult = null;
            window.initSMCaptcha({
                organization: 'P9usCUBauxft8eAmUXaZ', appendTo: 'mycap', lang: 'zh-cn',
                mode: 'spatial_select', maskBindClose: false,
                onSuccess: (r) => { window.__capResult = {ok: true}; },
                onError: (e) => { window.__capResult = {ok: false, e: String(e).slice(0,200)}; }
            }, (ret) => { window.__capResult = {cb: true}; });
        }""")
        for i in range(12):
            page.wait_for_timeout(700)
            info = page.evaluate(PROBE)
            print(f"[{i}]", json.dumps(info, ensure_ascii=False)[:1200])
        print("[result]", page.evaluate("() => window.__capResult"))
        page.screenshot(path=os.path.join(OUT, "diag2.png"))
        browser.close()


if __name__ == "__main__":
    main()
