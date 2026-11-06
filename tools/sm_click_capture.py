"""在真实验证码上点击并确认，捕获 verify 请求（URL/header/加密 body）与全部明文 log。

同时 hook 常见的序列化入口，尝试拿到 verify 之前的明文结构。
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
  // 记录所有被 stringify 的对象里含坐标字段的明文（求解器关心的明文结构）
  const oStr = JSON.stringify;
  window.__plain = [];
  JSON.stringify = function(v, ...rest){
    const s = oStr.call(this, v, ...rest);
    try {
      if (typeof s === 'string' && s.length < 4000 &&
          /"(x|y|coordinate|track|points|pos)"/i.test(s)) window.__plain.push(s);
    } catch(e){}
    return s;
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
            ctype = (resp.headers or {}).get("content-type", "")
            rec = {"url": url, "status": resp.status, "len": len(body),
                   "method": resp.request.method,
                   "req_headers": dict(resp.request.headers),
                   "req_body": resp.request.post_data}
            if len(body) < 400000:
                rec["body"] = body.decode("utf-8", "replace")
            recs.append(rec)
            with open(os.path.join(OUT, f"c_{safe_name(url)}.txt"), "wb") as fh:
                fh.write(body)

        page.on("response", on_resp)
        page.goto("https://chat.deepseek.com/sign_in", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1200)
        page.fill("input[type=tel]", "13800138000")
        page.click("text=发送验证码")
        box = None
        for i in range(30):
            page.wait_for_timeout(700)
            box = page.evaluate("""() => {
                const w = document.querySelector('[id$="_shumei_captcha_wrapper"]');
                if (!w) return null;
                const r = w.getBoundingClientRect();
                if (r.width < 50) return null;
                return {x:r.x, y:r.y, w:r.width, h:r.height};
            }""")
            if box:
                print(f"[widget] 第 {i} 次轮询命中 {box}")
                break
        print("[widget]", box)
        if not box:
            page.screenshot(path=os.path.join(OUT, "no_widget.png"))
            print("no widget")
            browser.close()
            return
        page.screenshot(path=os.path.join(OUT, "cap_before_click.png"))

        # 图片区高度 = 147/196 ≈ 0.75
        img_h = box["h"] * 0.75
        for rx, ry in [(0.3, 0.3), (0.6, 0.5), (0.8, 0.7)]:
            page.mouse.move(box["x"] + box["w"] * rx, box["y"] + img_h * ry)
            page.wait_for_timeout(120)
            page.mouse.down()
            page.wait_for_timeout(60)
            page.mouse.up()
            page.wait_for_timeout(600)
        page.screenshot(path=os.path.join(OUT, "cap_clicked.png"))

        # 确认按钮：wrapper 底部 49px 区域
        for sel in ["text=确认", "text=确定", "button", "[class*=confirm]", "[class*=btn]"]:
            try:
                el = page.query_selector(sel)
                if el and el.is_visible():
                    el.click(timeout=2000)
                    print(f"[ok] clicked {sel}")
                    break
            except Exception:
                continue
        else:
            # 兜底：点 wrapper 底部中央
            page.mouse.click(box["x"] + box["w"] / 2, box["y"] + box["h"] - 18)
            print("[ok] clicked bottom-center fallback")

        page.wait_for_timeout(4000)
        page.screenshot(path=os.path.join(OUT, "cap_after_confirm.png"))

        xhrs = page.evaluate("() => window.__xhrs || []")
        plains = page.evaluate("() => window.__plain || []")
        with open(os.path.join(OUT, "click_xhrs.json"), "w", encoding="utf-8") as fh:
            json.dump({"xhrs": xhrs, "plains": plains, "recs": recs}, fh, ensure_ascii=False, indent=1)

        print("\n=== 明文序列化候选 ===")
        for s in plains[-8:]:
            print(" ", s[:600])
        print("\n=== verify 相关 ===")
        for x in xhrs:
            if "verify" in x["u"] or "verify" in str(x.get("body", ""))[:200]:
                print(json.dumps(x, ensure_ascii=False)[:2000])
        browser.close()


if __name__ == "__main__":
    main()
