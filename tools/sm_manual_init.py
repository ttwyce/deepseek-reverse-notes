"""手动调用页面内的 initSMCaptcha 拉起验证码，稳定捕获 verify 报文。

deepseek 的弹窗触发受服务端风控评分影响，不一定每次都弹；
直接用捕获到的配置在页面里自建容器初始化，就能稳定走完 register→点击→verify。
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
            with open(os.path.join(OUT, f"m_{safe_name(url)}.txt"), "wb") as fh:
                fh.write(body)

        page.on("response", on_resp)
        page.goto("https://chat.deepseek.com/sign_in", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(2000)

        # 等 initSMCaptcha 可用
        for _ in range(20):
            ok = page.evaluate("() => typeof window.initSMCaptcha === 'function'")
            if ok:
                break
            page.wait_for_timeout(500)
        print("[initSMCaptcha ready]", ok)

        init = page.evaluate("""() => {
            const d = document.createElement('div');
            d.id = 'mycap';
            d.style.cssText = 'position:fixed;left:20px;top:20px;z-index:999999;width:320px;height:260px;';
            document.body.appendChild(d);
            window.__capResult = null;
            try {
                window.initSMCaptcha({
                    organization: 'P9usCUBauxft8eAmUXaZ',
                    appendTo: 'mycap',
                    lang: 'zh-cn',
                    mode: 'spatial_select',
                    maskBindClose: false,
                    onSuccess: (r) => { window.__capResult = {ok: true, r}; },
                    onError: (e) => { window.__capResult = {ok: false, e}; },
                    onClose: () => { window.__capResult = window.__capResult || {closed: true}; }
                }, (ret) => { window.__capResult = {cb: ret}; });
                return 'called';
            } catch (e) { return 'ERR:' + String(e); }
        }""")
        print("[init]", init)

        box = None
        for i in range(40):
            page.wait_for_timeout(700)
            box = page.evaluate("""() => {
                const w = document.querySelector('[id$="_shumei_captcha_wrapper"]');
                if (!w) return null;
                const r = w.getBoundingClientRect();
                if (r.width < 50) return null;
                return {x:r.x, y:r.y, w:r.width, h:r.height};
            }""")
            if box:
                print(f"[widget] 命中（第 {i} 次）{box}")
                break
        if not box:
            page.screenshot(path=os.path.join(OUT, "manual_nocap.png"))
            print("[dom]", page.evaluate("() => document.getElementById('mycap').innerHTML.slice(0,500)"))
            browser.close()
            return

        page.screenshot(path=os.path.join(OUT, "manual_cap.png"))
        img_h = box["h"] * 0.75
        for rx, ry in [(0.3, 0.3), (0.6, 0.5), (0.8, 0.7)]:
            page.mouse.move(box["x"] + box["w"] * rx, box["y"] + img_h * ry)
            page.wait_for_timeout(150)
            page.mouse.down()
            page.wait_for_timeout(80)
            page.mouse.up()
            page.wait_for_timeout(700)
        page.screenshot(path=os.path.join(OUT, "manual_clicked.png"))

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
            print("[confirm] fallback bottom click")

        page.wait_for_timeout(5000)
        page.screenshot(path=os.path.join(OUT, "manual_after.png"))

        xhrs = page.evaluate("() => window.__xhrs || []")
        result = page.evaluate("() => window.__capResult")
        print("\n[capResult]", json.dumps(result, ensure_ascii=False)[:1200])
        print("\n=== 网络明文（log/verify） ===")
        for x in xhrs:
            if "verify" in x["u"]:
                print(json.dumps(x, ensure_ascii=False)[:3000])
        with open(os.path.join(OUT, "manual_xhrs.json"), "w", encoding="utf-8") as fh:
            json.dump({"xhrs": xhrs, "result": result, "recs": recs}, fh, ensure_ascii=False, indent=1)
        browser.close()


if __name__ == "__main__":
    main()
