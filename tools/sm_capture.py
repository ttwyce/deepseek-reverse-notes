"""抓取数美验证码相关前端资源与接口流量。

只做被动观察：打开 DeepSeek 登录页，记录所有 fengkongcloud / shumei 域名的
请求与响应（JS 资源整份落盘，接口 JSON 存 work/sm/），用于后续协议复刻。
"""
import json
import os
import re
import time

from playwright.sync_api import sync_playwright

OUT = os.path.join("work", "sm")
os.makedirs(OUT, exist_ok=True)

HOSTS = ("fengkongcloud", "shumei", "smcp", "castatic", "captcha")
recs = []


def save(name, data: bytes):
    path = os.path.join(OUT, name)
    with open(path, "wb") as fh:
        fh.write(data)
    print(f"[saved] {path}  {len(data)} bytes")


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
            except Exception as exc:  # noqa: BLE001
                print(f"[skip] {url} {exc}")
                return
            ctype = (resp.headers or {}).get("content-type", "")
            recs.append({"url": url, "status": resp.status, "ctype": ctype,
                         "len": len(body), "req_method": resp.request.method,
                         "req_headers": dict(resp.request.headers),
                         "req_body": resp.request.post_data})
            safe = re.sub(r"[^A-Za-z0-9._-]+", "_", url.split("://", 1)[-1])[:150]
            if "javascript" in ctype or url.endswith(".js"):
                save(f"js_{safe}.js", body)
            else:
                save(f"raw_{safe}", body)

        page.on("response", on_resp)
        page.goto("https://chat.deepseek.com/sign_in", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(3000)
        page.screenshot(path=os.path.join(OUT, "signin.png"))

        # 尝试切到「密码登录」并提交一个空/假表单，触发验证码加载
        for sel in ["text=密码登录", "text=Password", "text=使用密码登录"]:
            try:
                page.click(sel, timeout=2500)
                print(f"[ok] clicked {sel}")
                break
            except Exception:
                continue
        page.wait_for_timeout(1500)
        page.screenshot(path=os.path.join(OUT, "signin2.png"))

        # 在页面里探测数美全局对象
        probe = page.evaluate("""() => {
            const out = {keys: [], win: []};
            try { out.win = Object.keys(window).filter(k => /sm|shumei|captcha|fengkong/i.test(k)); } catch(e){}
            return out;
        }""")
        print("[probe]", json.dumps(probe, ensure_ascii=False)[:1500])

        with open(os.path.join(OUT, "records.json"), "w", encoding="utf-8") as fh:
            json.dump(recs, fh, ensure_ascii=False, indent=1)
        print(f"\n共记录 {len(recs)} 条数美相关请求")
        for r in recs:
            print(f"  {r['status']:>3} {r['len']:>8} {r['req_method']:<4} {r['url'][:130]}")
        browser.close()


if __name__ == "__main__":
    main()
