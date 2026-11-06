from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
    ctx = b.new_context(viewport={"width":1366,"height":900}, locale="zh-CN", timezone_id="Asia/Shanghai")
    p = ctx.new_page()
    p.goto("https://chat.deepseek.com/sign_in", wait_until="domcontentloaded", timeout=60000)
    p.wait_for_timeout(5000)
    ok = p.evaluate("""() => {
        for (const el of document.querySelectorAll('.ds-button__content')) {
            if ((el.textContent||'').trim() === '密码登录') {
                const btn = el.closest('button') || el.parentElement;
                btn.click();
                return btn.className + ' | ' + btn.tagName;
            }
        }
        return null;
    }""")
    print("clicked:", ok)
    p.wait_for_timeout(3000)
    print("== inputs ==")
    for el in p.query_selector_all("input"):
        print("  ", el.get_attribute("type"), el.get_attribute("placeholder"))
    print("== text ==")
    print(p.inner_text("body")[:500])
    b.close()
