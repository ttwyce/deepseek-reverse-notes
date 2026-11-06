"""Hook 数美验证码初始化入口 + 网络层，捕获 initSMCaptcha 配置与 verify 报文。

做法：
1. add_init_script 把 window.initSMCaptcha 包一层，记录 deepseek 传入的 config；
2. 监听 fengkongcloud 的 verify 请求（含加密 body）；
3. 触发一次「发送验证码」；若验证码没弹出，就用捕获到的 config 手动 init 一次。
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
  window.__smCalls = [];
  let orig = window.initSMCaptcha;
  Object.defineProperty(window, 'initSMCaptcha', {
    configurable: true,
    get() { return orig; },
    set(v) {
      orig = function(...args) {
        try {
          window.__smCalls.push({
            t: Date.now(),
            cfg: JSON.parse(JSON.stringify(args[0] || {}, (k, val) =>
              typeof val === 'function' ? '[fn]' : val)),
            argc: args.length
          });
        } catch (e) { window.__smCalls.push({err: String(e)}); }
        return v.apply(this, args);
      };
    }
  });
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
            rec = {"url": url, "status": resp.status, "ctype": ctype, "len": len(body),
                   "method": resp.request.method,
                   "req_headers": dict(resp.request.headers),
                   "req_body": resp.request.post_data}
            if len(body) < 400000:
                rec["body"] = body.decode("utf-8", "replace")
            recs.append(rec)
            with open(os.path.join(OUT, f"h_{safe_name(url)}.txt"), "wb") as fh:
                fh.write(body)

        page.on("response", on_resp)
        page.goto("https://chat.deepseek.com/sign_in", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1500)
        page.fill("input[type=tel]", "13800138000")
        page.click("text=发送验证码")
        page.wait_for_timeout(6000)

        calls = page.evaluate("() => window.__smCalls")
        print("[initSMCaptcha calls]", json.dumps(calls, ensure_ascii=False, indent=1)[:4000])

        vis = page.evaluate("""() => {
            const w = document.querySelector('[id$="_shumei_captcha_wrapper"]');
            if (!w) return null;
            const r = w.getBoundingClientRect();
            return {x:r.x, y:r.y, w:r.width, h:r.height, cls: w.className};
        }""")
        print("[widget]", json.dumps(vis, ensure_ascii=False))

        if vis and vis["w"] > 50:
            pts = [(0.25, 0.25), (0.5, 0.4), (0.75, 0.55)]
            for rx, ry in pts:
                page.mouse.click(vis["x"] + vis["w"] * rx, vis["y"] + vis["h"] * 0.75 * ry)
                page.wait_for_timeout(500)
            page.screenshot(path=os.path.join(OUT, "hook_clicked.png"))
            for sel in ["text=确认", "text=确定"]:
                try:
                    page.click(sel, timeout=2000)
                    print(f"[ok] confirm {sel}")
                    break
                except Exception:
                    pass
            page.wait_for_timeout(5000)
        page.screenshot(path=os.path.join(OUT, "hook_after.png"))

        with open(os.path.join(OUT, "hook_records.json"), "w", encoding="utf-8") as fh:
            json.dump(recs, fh, ensure_ascii=False, indent=1)
        print(f"\n共 {len(recs)} 条")
        for x in recs:
            print(f"  {x['status']:>3} {x['len']:>8} {x['method']:<4} {x['url'][:150]}")
        browser.close()


if __name__ == "__main__":
    main()
