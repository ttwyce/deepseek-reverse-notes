"""导出页面侧的数美 SDK 配置（window._smConf）与内联脚本片段。"""
import json
import os

from playwright.sync_api import sync_playwright

OUT = os.path.join("work", "sm", "fp")
os.makedirs(OUT, exist_ok=True)


def main():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": 1440, "height": 900},
                            locale="zh-CN",
                            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                        "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"))
        pg = ctx.new_page()
        pg.goto("https://chat.deepseek.com/sign_in", wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(8000)

        conf = pg.evaluate("""() => {
            const out = {};
            try { out._smConf = window._smConf; } catch(e) {}
            try { out.smSdkKeys = Object.keys(window.SMSdk || {}); } catch(e) {}
            try { out.smReady = (window._smReadyFuncs || []).length; } catch(e) {}
            const scripts = [];
            for (const sc of document.querySelectorAll('script')) {
                const t = sc.textContent || '';
                if (/smConf|SMSdk|portal101|fengkong/.test(t)) {
                    scripts.push({src: sc.src || null, len: t.length, text: t.slice(0, 4000)});
                }
            }
            out.inline = scripts;
            const fpTag = [...document.querySelectorAll('script')].map(s => s.src).filter(Boolean)
                .filter(s => /fp\\.min|smcp|fengkong/.test(s));
            out.sdkScripts = fpTag;
            return out;
        }""")
        with open(os.path.join(OUT, "smconf.json"), "w", encoding="utf-8") as fh:
            json.dump(conf, fh, ensure_ascii=False, indent=1)

        print("_smConf =", json.dumps(conf.get("_smConf"), ensure_ascii=False)[:3000])
        print("SMSdk keys =", conf.get("smSdkKeys"))
        print("sdkScripts =", conf.get("sdkScripts"))
        for sc in conf.get("inline") or []:
            print("-" * 60, sc["src"], sc["len"])
            print(sc["text"][:1500])
        b.close()


if __name__ == "__main__":
    main()
