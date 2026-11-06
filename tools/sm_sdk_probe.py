"""探测页面内数美 SDK 的可调用接口，用于手动拉起验证码以捕获 verify 报文。"""
import json

from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                                  user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                              "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"))
        page = ctx.new_page()
        page.goto("https://chat.deepseek.com/sign_in", wait_until="networkidle", timeout=60000)
        page.wait_for_timeout(1500)

        out = page.evaluate("""() => {
            const r = {};
            r.smConf = window._smConf;
            r.sdkType = typeof window.SMSdk;
            r.sdkKeys = window.SMSdk ? Object.keys(window.SMSdk) : null;
            r.sdkProto = window.SMSdk ? Object.getOwnPropertyNames(Object.getPrototypeOf(window.SMSdk)) : null;
            r.initSrc = window.initSMCaptcha ? window.initSMCaptcha.toString().slice(0, 3000) : null;
            r.readyFuncs = Array.isArray(window._smReadyFuncs) ? window._smReadyFuncs.length : null;
            try { r.sdkJson = JSON.stringify(window.SMSdk, (k,v)=> typeof v==='function' ? 'fn:'+v.name : v).slice(0,3000); } catch(e) { r.sdkJson = String(e); }
            return r;
        }""")
        print(json.dumps(out, ensure_ascii=False, indent=1)[:6000])
        browser.close()


if __name__ == "__main__":
    main()
