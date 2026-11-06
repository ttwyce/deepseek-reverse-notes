"""验证「检测验证码 → 截图回传 → 相对坐标换算成页面点击」这条链路。

不接触真实账号与真实验证码：在本地注入一个与数美面板同结构的假 DOM，
只检验 login_page.py 里的选择器、截图与坐标换算逻辑是否正确。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import login_page as L  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

FAKE = """<!doctype html><meta charset="utf-8">
<style>
 body{margin:0;background:#111}
 .sm-captcha-wrap{position:fixed;left:120px;top:80px;width:340px;height:230px;
   background:linear-gradient(135deg,#1b2233,#2a3550);border:1px solid #3b4a6b;
   border-radius:8px;color:#dfe6f5;font:14px/1.6 sans-serif;padding:12px;box-sizing:border-box}
 .tip{font-size:13px;color:#9fb0d0;margin-bottom:8px}
 .grid{width:100%;height:150px;background:#0d1320;border-radius:6px}
</style>
<div class="sm-captcha-wrap">
  <div class="tip">请点击图中最小的蓝色圆锥</div>
  <div class="grid"></div>
</div>
<script>
 window.__clicks = [];
 document.addEventListener('click',
   e => window.__clicks.push([Math.round(e.clientX), Math.round(e.clientY)]), true);
</script>
"""


def main() -> int:
    ok = True
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.set_content(FAKE)
        page.wait_for_timeout(300)

        el, box = L.find_captcha(page)
        print(f"1) find_captcha 命中：{el is not None}  bbox={box}")
        ok &= el is not None and box is not None
        if el is None or box is None:
            browser.close()
            return 1

        png = el.screenshot()
        print(f"2) 元素截图：{len(png)} bytes  PNG 头={png[:8]!r}")
        ok &= len(png) > 2000 and png[:8] == b"\x89PNG\r\n\x1a\n"
        out = os.path.join("work", "_fake_captcha.png")
        with open(out, "wb") as fh:
            fh.write(png)
        print(f"   已写入 {out}")

        rx, ry = 0.5, 0.42
        x = box["x"] + box["width"] * rx
        y = box["y"] + box["height"] * ry
        page.mouse.click(x, y)
        page.wait_for_timeout(200)
        clicks = page.evaluate("window.__clicks")
        print(f"3) 相对坐标 ({rx},{ry}) → 页面坐标 ({x:.1f},{y:.1f})")
        print(f"   浏览器实际收到点击：{clicks}")
        inside = bool(clicks) and (
            box["x"] <= clicks[-1][0] <= box["x"] + box["width"]
            and box["y"] <= clicks[-1][1] <= box["y"] + box["height"]
        )
        print(f"   落点在验证码框内：{inside}")
        ok &= inside

        code_el, code_box = L.find_code_input(page)
        print(f"4) 无验证码输入框时 find_code_input 返回空：{code_el is None}")

        browser.close()

    print("\n结果：", "全部通过" if ok else "存在失败项")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
