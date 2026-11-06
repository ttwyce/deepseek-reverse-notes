"""抓取数美 deviceprofile（fp-it.portal101.cn）真实流量基线。

只做被动观察：打开 DeepSeek 登录页，把数美指纹 SDK 的请求/响应整份落盘，
同时导出 window 上的数美对象、cookie、localStorage，供纯协议复刻对照。
"""
import json
import os
import re
import time

from playwright.sync_api import sync_playwright

OUT = os.path.join("work", "sm", "fp")
os.makedirs(OUT, exist_ok=True)

HOSTS = ("portal101", "fengkongcloud", "fp-it")

recs = []


def safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:140]


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"),
            locale="zh-CN",
        )
        page = ctx.new_page()

        def on_req(req):
            url = req.url
            if not any(h in url for h in HOSTS):
                return
            recs.append({"phase": "req", "url": url, "method": req.method,
                         "headers": dict(req.headers), "post_data": req.post_data})

        def on_resp(resp):
            url = resp.url
            if not any(h in url for h in HOSTS):
                return
            item = {"phase": "resp", "url": url, "status": resp.status}
            try:
                body = resp.body()
                item["len"] = len(body)
                ctype = (resp.headers or {}).get("content-type", "")
                if "javascript" in ctype or url.endswith(".js"):
                    with open(os.path.join(OUT, "js_" + safe(url.split("://")[-1])), "wb") as fh:
                        fh.write(body)
                else:
                    item["body"] = body.decode("utf-8", "replace")[:20000]
            except Exception as exc:  # noqa: BLE001
                item["err"] = str(exc)
            recs.append(item)

        page.on("request", on_req)
        page.on("response", on_resp)

        page.goto("https://chat.deepseek.com/sign_in", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(9000)

        # 导出页面侧的设备 id 痕迹
        probe = page.evaluate("""() => {
            const out = {globals: [], cookie: document.cookie, ls: {}, ss: {}, win: []};
            for (const k of Object.keys(window)) {
                if (/^(sm|fp|_sm|shumei|fengkong|Fp)/i.test(k)) {
                    out.globals.push(k);
                    try { out.win[k] = typeof window[k]; } catch (e) {}
                }
            }
            try { for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); out.ls[k] = localStorage.getItem(k); } } catch (e) {}
            try { for (let i = 0; i < sessionStorage.length; i++) { const k = sessionStorage.key(i); out.ss[k] = sessionStorage.getItem(k); } } catch (e) {}
            return out;
        }""")
        with open(os.path.join(OUT, "probe.json"), "w", encoding="utf-8") as fh:
            json.dump(probe, fh, ensure_ascii=False, indent=1)

        # 再点一次「密码登录」触发可能的指纹上报
        for sel in ["text=密码登录", "text=Password", "input[name=password]"]:
            try:
                page.click(sel, timeout=3000)
                print(f"[ok] clicked {sel}")
                break
            except Exception:
                continue
        page.wait_for_timeout(6000)
        page.screenshot(path=os.path.join(OUT, "signin.png"))

        with open(os.path.join(OUT, "records.json"), "w", encoding="utf-8") as fh:
            json.dump(recs, fh, ensure_ascii=False, indent=1)

        print(f"\n共记录 {len(recs)} 条数美相关网络事件")
        for r in recs:
            if r["phase"] == "req":
                print(f"  REQ  {r['method']:<4} {r['url'][:150]}")
            else:
                print(f"  RESP {r['status']:>3} {r.get('len', 0):>8} {r['url'][:150]}")
        print("\nglobals:", probe.get("globals"))
        print("cookie:", probe.get("cookie")[:400])
        print("ls keys:", list((probe.get("ls") or {}).keys())[:20])
        browser.close()


if __name__ == "__main__":
    main()
