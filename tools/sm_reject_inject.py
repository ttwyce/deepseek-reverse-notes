"""改写 register 响应把 riskLevel 从 PASS 改成 REJECT，强制 SDK 展示验证码，
然后模拟点击并确认，捕获 verify 请求的完整 URL 参数与加密 body。

这是拿 verify 报文的关键一步：SDK 只有在需要验证时才渲染面板。
"""
import json
import os
import re

from playwright.sync_api import sync_playwright

OUT = os.path.join("work", "sm")
os.makedirs(OUT, exist_ok=True)
recs = []

HOOK = r"""
(() => {
  window.__xhrs = [];
  const oOpen = XMLHttpRequest.prototype.open, oSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.open = function(m,u,...r){ this.__u=u; this.__m=m; return oOpen.call(this,m,u,...r); };
  XMLHttpRequest.prototype.send = function(b){
    if (String(this.__u).includes('fengkongcloud')) {
      window.__xhrs.push({m:this.__m,u:String(this.__u),body: typeof b==='string'? b : String(b)});
    }
    return oSend.call(this,b);
  };
  const oFetch = window.fetch;
  window.fetch = function(...a){
    try { const u=String(a[0]&&a[0].url?a[0].url:a[0]);
      if(u.includes('fengkongcloud')) window.__xhrs.push({m:'fetch',u,body:a[1]&&a[1].body?String(a[1].body):null});
    } catch(e){}
    return oFetch.apply(this,a);
  };
})();
"""


def safe_name(url: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", url.split("://", 1)[-1])[:140]


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                                  user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                              "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"))
        ctx.add_init_script(HOOK)
        page = ctx.new_page()

        def on_register(route):
            try:
                resp = route.fetch()
                body = resp.text()
                new = body.replace('"riskLevel":"PASS"', '"riskLevel":"REJECT"')
                print(f"[route] register 改写 PASS→REJECT: {body[:120]}...")
                route.fulfill(response=resp, body=new)
            except Exception as exc:
                print("[route] fail", exc)
                route.continue_()

        page.route("**/ca/v1/register*", on_register)

        def on_resp(resp):
            url = resp.url
            if "fengkongcloud" not in url:
                return
            try:
                body = resp.body()
            except Exception:
                body = b""
            rec = {"url": url, "status": resp.status, "len": len(body),
                   "method": resp.request.method,
                   "req_headers": dict(resp.request.headers),
                   "req_body": resp.request.post_data}
            if len(body) < 400000:
                rec["body"] = body.decode("utf-8", "replace")
            recs.append(rec)
            with open(os.path.join(OUT, f"r_{safe_name(url)}.txt"), "wb") as fh:
                fh.write(body)

        page.on("response", on_resp)
        page.goto("https://chat.deepseek.com/sign_in", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1500)

        init = page.evaluate("""() => {
            const d = document.createElement('div');
            d.id = 'mycap';
            d.style.cssText = 'position:fixed;left:20px;top:20px;z-index:999999;width:320px;';
            document.body.appendChild(d);
            window.__capResult = null;
            window.initSMCaptcha({
                organization: 'P9usCUBauxft8eAmUXaZ',
                appendTo: 'mycap', lang: 'zh-cn', mode: 'spatial_select',
                maskBindClose: false,
                onSuccess: (r) => { window.__capResult = {ok: true, r}; },
                onError: (e) => { window.__capResult = {ok: false, e}; },
                onClose: () => { window.__capResult = window.__capResult || {closed: true}; }
            }, (ret) => { window.__capResult = {cb: ret}; });
            return 'called';
        }""")
        print("[init]", init)

        box = None
        for i in range(30):
            page.wait_for_timeout(700)
            box = page.evaluate("""() => {
                const w = document.querySelector('[id$="_shumei_captcha_wrapper"]');
                if (!w) return null;
                const r = w.getBoundingClientRect();
                if (r.width < 50 || r.height < 50) return null;
                return {x:r.x, y:r.y, w:r.width, h:r.height};
            }""")
            if box:
                print(f"[widget] 第 {i} 次命中 {box}")
                break
        if not box:
            print("[dom]", page.evaluate("() => document.getElementById('mycap').innerHTML.slice(0,300)"))
            page.screenshot(path=os.path.join(OUT, "reject_nocap.png"))
            browser.close()
            return

        page.screenshot(path=os.path.join(OUT, "reject_cap.png"))
        img_h = box["h"] * 0.75
        clicks = []
        for rx, ry in [(0.3, 0.3), (0.6, 0.5), (0.8, 0.7)]:
            cx, cy = box["x"] + box["w"] * rx, box["y"] + img_h * ry
            page.mouse.move(cx, cy)
            page.wait_for_timeout(150)
            page.mouse.down()
            page.wait_for_timeout(80)
            page.mouse.up()
            clicks.append([round(rx, 3), round(ry, 3)])
            page.wait_for_timeout(700)
        page.screenshot(path=os.path.join(OUT, "reject_clicked.png"))

        clicked = page.evaluate("""() => {
            const root = document.getElementById('mycap');
            const cands = [...root.querySelectorAll('*')].filter(e => {
                const t = (e.innerText || '').trim();
                return t && t.length <= 6 && /确认|确定|verify|提交/i.test(t);
            });
            if (cands.length) { cands[0].click(); return 'clicked:' + cands[0].innerText.trim(); }
            return 'none';
        }""")
        print("[confirm]", clicked)
        if clicked == "none":
            page.mouse.click(box["x"] + box["w"] / 2, box["y"] + box["h"] - 16)
            print("[confirm] fallback")
        page.wait_for_timeout(5000)
        page.screenshot(path=os.path.join(OUT, "reject_after.png"))

        xhrs = page.evaluate("() => window.__xhrs || []")
        result = page.evaluate("() => window.__capResult")
        print("\n[capResult]", json.dumps(result, ensure_ascii=False)[:1500])
        print("\n=== verify 请求 ===")
        for x in xhrs:
            if "verify" in x["u"]:
                print(json.dumps(x, ensure_ascii=False)[:3000])
        with open(os.path.join(OUT, "reject_xhrs.json"), "w", encoding="utf-8") as fh:
            json.dump({"xhrs": xhrs, "result": result, "recs": recs, "clicks": clicks},
                      fh, ensure_ascii=False, indent=1)
        print("\n[all xhr urls]")
        for x in xhrs:
            print("  ", x["m"], x["u"][:140])
        browser.close()


if __name__ == "__main__":
    main()
