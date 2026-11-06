"""在真实页面里截取数美 fp 加密前的明文 JSON（gzip 之前的那份）。

原理：主流程 `_0x3d7259` 先给对象加 `uq` 签名，再 `gzip(obj)`（内部 JSON.stringify）。
所以包装 JSON.stringify，凡是结果里带 "uq" 字段的，就是完整明文指纹对象。
同时仍记录 deviceprofile 请求/响应，便于对照密文长度。
"""
import json
import os
import time

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", os.path.join("tools", "pw-browsers"))

from playwright.sync_api import sync_playwright

OUT = os.path.join("work", "sm", "fp")
os.makedirs(OUT, exist_ok=True)

HOOK = r"""
(() => {
  window.__smPlain = [];
  const orig = JSON.stringify;
  JSON.stringify = function (v, r, s) {
    const out = orig.apply(this, arguments);
    try {
      if (typeof out === 'string' && out.length > 400 && out.indexOf('"uq"') >= 0) {
        window.__smPlain.push({t: Date.now(), str: out});
      }
    } catch (e) {}
    return out;
  };
  try {
    const o2 = window.XMLHttpRequest && window.XMLHttpRequest.prototype;
    if (o2 && o2.send) {
      const os = o2.send;
      o2.send = function (body) {
        try {
          if (typeof body === 'string' && body.indexOf('deviceprofile') < 0 && body.indexOf('"data"') >= 0) {
            window.__smBodies = window.__smBodies || [];
            window.__smBodies.push({t: Date.now(), len: body.length, body: body});
          }
        } catch (e) {}
        return os.apply(this, arguments);
      };
    }
  } catch (e) {}
})();
"""


def main():
    seen = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"),
            locale="zh-CN",
        )
        ctx.add_init_script(HOOK)
        page = ctx.new_page()

        def on_resp(resp):
            if "deviceprofile" in resp.url:
                try:
                    seen.append({"url": resp.url, "status": resp.status, "body": resp.text()})
                except Exception:
                    pass

        page.on("response", on_resp)
        page.goto("https://chat.deepseek.com/sign_in", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(9000)

        plain = page.evaluate("() => window.__smPlain || []")
        bodies = page.evaluate("() => window.__smBodies || []")
        cookies = page.evaluate("() => document.cookie")
        ls = page.evaluate("""() => { const o={}; try{for(let i=0;i<localStorage.length;i++){const k=localStorage.key(i);o[k]=localStorage.getItem(k);}}catch(e){} return o; }""")

    with open(os.path.join(OUT, "plain.json"), "w", encoding="utf-8") as fh:
        json.dump(plain, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, "bodies.json"), "w", encoding="utf-8") as fh:
        json.dump(bodies, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(OUT, "env.json"), "w", encoding="utf-8") as fh:
        json.dump({"cookie": cookies, "ls": ls, "resp": seen}, fh, ensure_ascii=False, indent=1)

    print(f"[plain] {len(plain)} 命中")
    for i, it in enumerate(plain):
        print(f"  #{i} len={len(it['str'])} head={it['str'][:300]}")
    print(f"[bodies] {len(bodies)} 条")
    for i, it in enumerate(bodies):
        print(f"  #{i} len={it['len']} head={it['body'][:200]}")
    print("[resp]", [(s.get('status'), s.get('body', '')[:160]) for s in seen])
    print("[ls keys]", list(ls.keys()))


if __name__ == "__main__":
    main()
