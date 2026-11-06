from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
    ctx = b.new_context(viewport={"width":1366,"height":900}, locale="zh-CN", timezone_id="Asia/Shanghai")
    p = ctx.new_page()
    p.goto("https://chat.deepseek.com/sign_in", wait_until="domcontentloaded", timeout=60000)
    p.wait_for_timeout(6000)
    print("== text ==")
    print(p.inner_text("body")[:1200])
    print("== inputs ==")
    for el in p.query_selector_all("input"):
        print(" input", el.get_attribute("type"), el.get_attribute("name"), el.get_attribute("placeholder"))
    print("== buttons ==")
    for el in p.query_selector_all("button, div[role=button], a[role=button]"):
        t = (el.inner_text() or "").strip().replace("\n"," ")
        if t: print(" btn:", t[:60])
    b.close()
