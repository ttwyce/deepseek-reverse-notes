from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
    ctx = b.new_context(viewport={"width":1366,"height":900}, locale="zh-CN", timezone_id="Asia/Shanghai")
    p = ctx.new_page()
    p.goto("https://chat.deepseek.com/sign_in", wait_until="domcontentloaded", timeout=60000)
    p.wait_for_timeout(5000)
    r = p.evaluate("""() => {
        const out = [];
        const walk = document.querySelectorAll('*');
        for (const el of walk) {
            const t = (el.textContent||'').trim();
            if (t === '密码登录' && el.children.length <= 1) {
                const cs = getComputedStyle(el);
                out.push({tag: el.tagName, cls: el.className,
                          vis: cs.visibility, disp: cs.display,
                          op: cs.opacity, w: el.offsetWidth, h: el.offsetHeight});
            }
        }
        return out;
    }""")
    for x in r: print(x)
    # 尝试对可见元素点击
    ok = p.evaluate("""() => {
        for (const el of document.querySelectorAll('*')) {
            if ((el.textContent||'').trim() === '密码登录' && el.offsetWidth > 0) {
                el.click(); return el.className;
            }
        }
        return null;
    }""")
    print("clicked:", ok)
    p.wait_for_timeout(2500)
    print("== inputs ==")
    for el in p.query_selector_all("input"):
        print("  ", el.get_attribute("type"), el.get_attribute("placeholder"))
    b.close()
