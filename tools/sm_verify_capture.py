"""用本地缓存的 captcha-sdk.min.js / style.min.css 拦截供给，保证面板真正渲染；
同时把 register 响应改写为 REJECT 强制出题，模拟点击后捕获 verify 报文。
"""
import json
import os
import re

from playwright.sync_api import sync_playwright

OUT = os.path.join("work", "sm")
SDK = open(os.path.join(OUT, "captcha-sdk.min.js"), "rb").read()
CSS = open(os.path.join(OUT, "r_castatic.fengkongcloud.cn_pr_auto-build_v1.0.4-210_style.min.css.txt"), "rb").read()

HOOK = r"""
(() => {
  window.__xhrs = [];
  const oOpen = XMLHttpRequest.prototype.open, oSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(m,u,...r){ this.__u=String(u); this.__m=m; return oOpen.call(this,m,u,...r); };
  XMLHttpRequest.prototype.send = function(b){
    if (this.__u.includes('fengkongcloud')) window.__xhrs.push({kind:'xhr', m:this.__m, u:this.__u, body: typeof b==='string'? b : String(b)});
    return oSend.call(this,b);
  };
  const oFetch = window.fetch;
  window.fetch = function(...a){
    try { const u=String(a[0]&&a[0].url?a[0].url:a[0]);
      if(u.includes('fengkongcloud')) window.__xhrs.push({kind:'fetch', m:(a[1]&&a[1].method)||'GET', u, body:a[1]&&a[1].body?String(a[1].body):null});
    } catch(e){}
    return oFetch.apply(this,a);
  };
  const oBeacon = navigator.sendBeacon && navigator.sendBeacon.bind(navigator);
  if (oBeacon) navigator.sendBeacon = function(u, d){ window.__xhrs.push({kind:'beacon', u:String(u), body:String(d)}); return oBeacon(u,d); };
  // 记录 Image 打点
  const oImg = window.Image;
  window.Image = function(...a){ const im = new oImg(...a); const d = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype,'src');
    Object.defineProperty(im,'src',{set(v){ window.__xhrs.push({kind:'img', u:String(v)}); d.set.call(im,v); }, get(){ return d.get.call(im); }});
    return im; };
})();
"""


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                                  user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                              "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"))
        ctx.add_init_script(HOOK)
        page = ctx.new_page()

        def on_route(route):
            url = route.request.url
            try:
                if "captcha-sdk.min.js" in url:
                    route.fulfill(status=200, content_type="application/javascript", body=SDK)
                    return
                if "style.min.css" in url:
                    route.fulfill(status=200, content_type="text/css", body=CSS)
                    return
                if "/ca/v1/register" in url:
                    resp = route.fetch()
                    body = resp.text()
                    new = body.replace('"riskLevel":"PASS"', '"riskLevel":"REJECT"')
                    print("[route] register →", new[:130].replace("\n", " "))
                    route.fulfill(response=resp, body=new)
                    return
            except Exception as exc:
                print("[route] err", url[:80], exc)
            route.continue_()

        page.route(re.compile(r"fengkongcloud\.cn/.*"), on_route)
        page.on("requestfailed", lambda r: print("[reqfail]", r.url[:110], r.failure))

        page.goto("https://chat.deepseek.com/sign_in", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1200)

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
                onError: (e) => { window.__capResult = {ok: false, e}; },
                onClose: () => { window.__capResult = window.__capResult || {closed: true}; }
            }, (ret) => { window.__capResult = {cb: ret}; });
        }""")

        box = None
        for i in range(24):
            page.wait_for_timeout(600)
            box = page.evaluate("""() => {
                const w = document.querySelector('[id$="_shumei_captcha_wrapper"]');
                if (!w) return null;
                const r = w.getBoundingClientRect();
                if (r.width < 50 || r.height < 50) return {bad:[Math.round(r.width),Math.round(r.height)]};
                return {x:r.x, y:r.y, w:r.width, h:r.height};
            }""")
            if box and "x" in box:
                print(f"[widget] tick {i} 渲染成功 {box}")
                break
            box = None
        if not box:
            print("[fail] 仍未渲染", page.evaluate("() => { const w=document.querySelector('[id$=\"_shumei_captcha_wrapper\"]'); return w? w.outerHTML.slice(0,400):'no wrapper'; }"))
            page.screenshot(path=os.path.join(OUT, "cap_norender.png"))
            browser.close()
            return

        page.screenshot(path=os.path.join(OUT, "cap_rendered.png"))
        img_h = box["h"] * 0.75
        clicks = []
        for rx, ry in [(0.3, 0.32), (0.55, 0.55), (0.75, 0.72)]:
            cx, cy = box["x"] + box["w"] * rx, box["y"] + img_h * ry
            page.mouse.move(cx - 8, cy - 8)
            page.wait_for_timeout(90)
            page.mouse.move(cx, cy, steps=4)
            page.wait_for_timeout(60)
            page.mouse.down()
            page.wait_for_timeout(70)
            page.mouse.up()
            clicks.append({"rel": [round(rx, 3), round(ry, 3)], "px": [round(cx, 1), round(cy, 1)]})
            page.wait_for_timeout(600)
        page.screenshot(path=os.path.join(OUT, "cap_clicked.png"))
        print("[clicks]", json.dumps(clicks))

        # 确认按钮：优先按文本，其次按底部区域坐标
        conf = page.evaluate("""() => {
            const root = document.getElementById('mycap');
            const all = [...root.querySelectorAll('*')];
            const t = all.filter(e => { const s=(e.innerText||'').trim(); return s && s.length<=8 && /确认|确定|提交|验证/i.test(s) && e.children.length===0; });
            if (t.length) { const r=t[0].getBoundingClientRect(); t[0].click(); return {by:'text', txt:t[0].innerText.trim(), rect:[r.x,r.y,r.width,r.height]}; }
            const btn = all.filter(e => /btn|button|confirm|submit/i.test(e.className||''));
            if (btn.length) { const r=btn[0].getBoundingClientRect(); btn[0].click(); return {by:'class', cls:btn[0].className, rect:[r.x,r.y,r.width,r.height]}; }
            return {by:'none'};
        }""")
        print("[confirm]", conf)
        if conf.get("by") == "none":
            page.mouse.click(box["x"] + box["w"] / 2, box["y"] + box["h"] - 18)
            print("[confirm] fallback 点击底部中心")

        page.wait_for_timeout(5000)
        page.screenshot(path=os.path.join(OUT, "cap_after.png"))
        xhrs = page.evaluate("() => window.__xhrs || []")
        result = page.evaluate("() => window.__capResult")
        print("\n[capResult]", json.dumps(result, ensure_ascii=False)[:2000])
        print("\n=== 全部数美请求 ===")
        for x in xhrs:
            print(" ", x.get("kind"), x.get("m"), x.get("u", "")[:150])
        print("\n=== verify 明细 ===")
        for x in xhrs:
            if "verify" in (x.get("u") or ""):
                print(json.dumps(x, ensure_ascii=False))
        with open(os.path.join(OUT, "verify_capture.json"), "w", encoding="utf-8") as fh:
            json.dump({"xhrs": xhrs, "result": result, "clicks": clicks, "box": box, "confirm": conf},
                      fh, ensure_ascii=False, indent=1)
        browser.close()


if __name__ == "__main__":
    main()
