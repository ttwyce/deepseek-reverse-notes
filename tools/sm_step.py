"""分步诊断：只把 captcha-sdk.min.js 换成本地缓存（并在头部打标记），
其余请求全部放行，确认 SDK 是否真正执行、面板是否渲染。"""
import json
import os
import re

from playwright.sync_api import sync_playwright

OUT = os.path.join("work", "sm")
SDK = b"window.__sdkLoaded=(window.__sdkLoaded||0)+1;\n" + open(os.path.join(OUT, "captcha-sdk.min.js"), "rb").read()

PROBE = r"""() => {
  const w = document.querySelector('[id$="_shumei_captcha_wrapper"]');
  const r = w ? w.getBoundingClientRect() : null;
  const iw = w ? w.querySelector('[class*="img_wrapper"]') : null;
  const ir = iw ? iw.getBoundingClientRect() : null;
  return {
    sdkLoaded: window.__sdkLoaded || 0,
    scripts: [...document.querySelectorAll('script[src]')].map(s=>s.src.split('/').pop()),
    wrapper: r ? [Math.round(r.x),Math.round(r.y),Math.round(r.width),Math.round(r.height)] : null,
    imgWrapper: ir ? [Math.round(ir.width),Math.round(ir.height)] : null,
    wDisplay: w ? getComputedStyle(w).display : null,
    wParentDisplay: w && w.parentElement ? getComputedStyle(w.parentElement).display : null,
    html: w ? w.innerHTML.length : 0
  };
}"""


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                                  user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                              "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"))
        page = ctx.new_page()
        seen = []

        def on_route(route):
            url = route.request.url
            if "captcha-sdk.min.js" in url:
                seen.append(url)
                route.fulfill(status=200, content_type="application/javascript", body=SDK)
                return
            route.continue_()

        page.route(re.compile(r"fengkongcloud\.cn/.*"), on_route)
        page.goto("https://chat.deepseek.com/sign_in", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1000)
        page.evaluate("""() => {
            const d = document.createElement('div');
            d.id = 'mycap';
            d.style.cssText = 'position:fixed;left:20px;top:20px;z-index:999999;width:340px;';
            document.body.appendChild(d);
            window.__capResult = null;
            window.initSMCaptcha({
                organization: 'P9usCUBauxft8eAmUXaZ', appendTo: 'mycap', lang: 'zh-cn',
                mode: 'spatial_select', maskBindClose: false,
                onSuccess: (r) => { window.__capResult = {ok: true, r}; },
                onError: (e) => { window.__capResult = {ok: false, e}; }
            }, (ret) => { window.__capResult = {cb: ret}; });
        }""")
        for i in range(20):
            page.wait_for_timeout(500)
            print(f"[{i}]", json.dumps(page.evaluate(PROBE), ensure_ascii=False))
        print("[intercepted sdk]", seen)
        print("[result]", json.dumps(page.evaluate("() => window.__capResult"), ensure_ascii=False)[:600])
        page.screenshot(path=os.path.join(OUT, "step_end.png"))
        browser.close()


if __name__ == "__main__":
    main()
