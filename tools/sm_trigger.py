"""触发数美验证码并捕获 register/verify 全量流量。

流程：打开 chat.deepseek.com/sign_in → 读 window._smConf → 填一个手机号 →
点「发送验证码」触发人机验证 → 保存 fengkongcloud 域名的请求与响应原文。
"""
import json
import os
import re

from playwright.sync_api import sync_playwright

OUT = os.path.join("work", "sm")
os.makedirs(OUT, exist_ok=True)
HOSTS = ("fengkongcloud", "captcha")
recs = []


def safe_name(url: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", url.split("://", 1)[-1])[:140]


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"),
        )
        page = ctx.new_page()

        def on_resp(resp):
            url = resp.url
            if not any(h in url for h in HOSTS):
                return
            try:
                body = resp.body()
            except Exception:
                return
            ctype = (resp.headers or {}).get("content-type", "")
            rec = {"url": url, "status": resp.status, "ctype": ctype, "len": len(body),
                   "method": resp.request.method,
                   "req_headers": dict(resp.request.headers),
                   "req_body": resp.request.post_data}
            if "json" in ctype or len(body) < 200000:
                rec["body"] = body.decode("utf-8", "replace")
            recs.append(rec)
            name = safe_name(url)
            with open(os.path.join(OUT, f"cap_{name}.txt"), "wb") as fh:
                fh.write(body)

        page.on("response", on_resp)
        page.goto("https://chat.deepseek.com/sign_in", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(2000)

        conf = page.evaluate("() => ({conf: window._smConf, sdk: typeof window.SMSdk, init: typeof window.initSMCaptcha})")
        print("[smConf]", json.dumps(conf, ensure_ascii=False)[:1200])

        # 切到手机号登录并填号
        for sel in ["text=手机号登录", "text=验证码登录"]:
            try:
                page.click(sel, timeout=2000)
                break
            except Exception:
                pass
        inputs = page.evaluate("""() => [...document.querySelectorAll('input')].map(i => ({
            type: i.type, ph: i.placeholder, name: i.name, id: i.id, cls: i.className}))""")
        print("[inputs]", json.dumps(inputs, ensure_ascii=False)[:1200])

        filled = False
        for sel in ["input[type=tel]", "input[placeholder*='手机']", "input[placeholder*='电话']"]:
            try:
                page.fill(sel, "13800138000", timeout=2500)
                filled = True
                print(f"[ok] filled {sel}")
                break
            except Exception:
                continue
        if not filled:
            print("[warn] 未找到手机号输入框，尝试 email 框")
            try:
                page.fill("input", "probe@example.com", timeout=2500)
            except Exception:
                pass
        page.wait_for_timeout(800)

        btns = page.evaluate("""() => [...document.querySelectorAll('button,div[role=button],a')]
            .map(b => (b.innerText||'').trim()).filter(t => t && t.length < 20).slice(0, 40)""")
        print("[buttons]", json.dumps(btns, ensure_ascii=False)[:1200])

        for sel in ["text=发送验证码", "button:has-text('发送')", "text=获取验证码", "text=登录"]:
            try:
                page.click(sel, timeout=2500)
                print(f"[ok] clicked {sel}")
                break
            except Exception:
                continue

        page.wait_for_timeout(6000)
        page.screenshot(path=os.path.join(OUT, "trigger.png"), full_page=False)
        # 页面里是否出现数美容器
        sm = page.evaluate("""() => {
            const ids = [...document.querySelectorAll('[id*=sm],[class*=sm-],[id*=captcha],[class*=captcha]')]
              .slice(0,20).map(e => ({tag:e.tagName, id:e.id, cls:e.className, w:e.offsetWidth, h:e.offsetHeight}));
            return {ids, sdkKeys: Object.keys(window).filter(k=>/sm|shumei|captcha/i.test(k))};
        }""")
        print("[sm-dom]", json.dumps(sm, ensure_ascii=False)[:2000])

        with open(os.path.join(OUT, "trigger_records.json"), "w", encoding="utf-8") as fh:
            json.dump(recs, fh, ensure_ascii=False, indent=1)
        print(f"\n共 {len(recs)} 条数美请求")
        for r in recs:
            print(f"  {r['status']:>3} {r['len']:>8} {r['method']:<4} {r['url'][:150]}")
        browser.close()


if __name__ == "__main__":
    main()
