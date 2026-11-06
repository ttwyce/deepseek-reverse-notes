"""观察数美 widget 生命周期：init 后按时间点 dump DOM 与截图，定位弹窗为何不出现。"""
import json
import os

from playwright.sync_api import sync_playwright

OUT = os.path.join("work", "sm")
os.makedirs(OUT, exist_ok=True)

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
          window.__smCalls.push({cfg: JSON.parse(JSON.stringify(args[0] || {}, (k, val) =>
            typeof val === 'function' ? '[fn]' : val))});
        } catch (e) {}
        window.__smInst = v;
        return v.apply(this, args);
      };
    }
  });
  // 记录 XHR / fetch 全部 fengkongcloud 交互（含加密 body 明文由 SDK 传入的部分）
  const origOpen = XMLHttpRequest.prototype.open;
  const origSend = XMLHttpRequest.prototype.send;
  window.__xhrs = [];
  XMLHttpRequest.prototype.open = function(m, u, ...rest) {
    this.__u = u; this.__m = m;
    return origOpen.call(this, m, u, ...rest);
  };
  XMLHttpRequest.prototype.send = function(body) {
    if (String(this.__u).includes('fengkongcloud')) {
      window.__xhrs.push({m: this.__m, u: String(this.__u), body: typeof body === 'string' ? body : String(body)});
    }
    return origSend.call(this, body);
  };
  const origFetch = window.fetch;
  window.fetch = function(...args) {
    try {
      const u = String(args[0] && args[0].url ? args[0].url : args[0]);
      if (u.includes('fengkongcloud')) {
        window.__xhrs.push({m: 'fetch', u, body: args[1] && args[1].body ? String(args[1].body) : null});
      }
    } catch (e) {}
    return origFetch.apply(this, args);
  };
})();
"""

DUMP = """() => {
  const all = [...document.querySelectorAll('*')].filter(e =>
      (e.id && /shumei|sm-captcha|captcha/i.test(e.id)) ||
      (typeof e.className === 'string' && /shumei|captcha/i.test(e.className)));
  return all.slice(0, 30).map(e => ({tag: e.tagName, id: e.id,
      cls: (typeof e.className === 'string' ? e.className : '').slice(0, 80),
      w: e.offsetWidth, h: e.offsetHeight,
      disp: getComputedStyle(e).display, vis: getComputedStyle(e).visibility}));
}"""


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                                  user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                              "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"))
        ctx.add_init_script(HOOK)
        page = ctx.new_page()
        page.goto("https://chat.deepseek.com/sign_in", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1200)
        page.fill("input[type=tel]", "13800138000")
        page.click("text=发送验证码")

        for i, wait in enumerate([1500, 2000, 3000, 4000]):
            page.wait_for_timeout(wait)
            dom = page.evaluate(DUMP)
            page.screenshot(path=os.path.join(OUT, f"life_{i}.png"))
            print(f"\n--- t={sum([1500,2000,3000,4000][:i+1])}ms  elements={len(dom)}")
            for d in dom[:12]:
                print("   ", json.dumps(d, ensure_ascii=False))

        print("\n[xhrs]", json.dumps(page.evaluate("() => window.__xhrs || []"), ensure_ascii=False)[:3000])
        print("\n[calls]", json.dumps(page.evaluate("() => window.__smCalls || []"), ensure_ascii=False)[:800])
        browser.close()


if __name__ == "__main__":
    main()
