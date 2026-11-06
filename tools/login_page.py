# -*- coding: utf-8 -*-
"""本地登录页面：网页里输入账号密码 → 后端驱动真实浏览器登录 →
触发数美滑块/点选时把验证码截图回传到网页上让用户自己点（全程不跳官网）。

用法：
    .\\.venv\\Scripts\\python.exe tools\\login_page.py
    # 浏览器打开 http://127.0.0.1:8765

可选参数：
    --port 8765     监听端口
    --visible       让后台浏览器窗口可见（默认移到屏幕外，不打扰）
    --headless      无头模式（数美可能识别，仅调试用）

架构：
    HTTP 服务（主线程） ←→ 共享 STATE ←→ 浏览器线程（Playwright sync）
    浏览器线程：执行命令、轮询页面状态、截取验证码/整页视图。

两种视图：
    - 验证码视图：自动定位验证码元素，放大显示，点击即精确落到该元素上
    - 整页视图  ：整个浏览器视口的截图，点哪里就点浏览器哪里（兜底）

产出：
    work\\auth_token.enc / work\\pw_auth_state.enc（DPAPI 加密）
"""
from __future__ import annotations

import json
import os
import queue
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(r"F:\dshh\deepseeka")
WORK = ROOT / "work"
CHROME = ROOT / "tools" / "pw-browsers" / "chromium-1248" / "chrome-win64" / "chrome.exe"

# Playwright 浏览器按工作区约定装在 tools\pw-browsers，未设环境变量时自动指过去
_BROWSERS = str(ROOT / "tools" / "pw-browsers")
if os.path.isdir(_BROWSERS):
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", _BROWSERS)

sys.path.insert(0, str(ROOT / "tools"))

SIGN_IN = "https://chat.deepseek.com/sign_in"
VW, VH = 1280, 900  # 视口尺寸，整页视图的坐标基准

# ------------------------------------------------------------------ 共享状态

STATE: dict = {
    "stage": "idle",     # idle|starting|submitting|captcha|mfa_code|done|error
    "message": "请输入账号和密码",
    "url": "",
    "log": [],
    "captcha_seq": 0,
    "captcha_w": 0,
    "captcha_h": 0,
    "has_captcha": False,
    "vp_seq": 0,
    "token_info": None,
    "error": None,
    "busy": False,
}
LOCK = threading.Lock()
CMDS: "queue.Queue[tuple]" = queue.Queue()
CAPTCHA = {"seq": 0, "png": b""}
VIEWPORT = {"seq": 0, "png": b""}
# Playwright 的 sync API 把 greenlet 绑在创建它的线程上，
# 因此 start() 与 run() 必须在同一个线程里顺序执行；用事件触发懒启动。
START_EVENT = threading.Event()


def set_state(**kw) -> None:
    with LOCK:
        STATE.update(kw)


def get_state(key: str, default=None):
    with LOCK:
        return STATE.get(key, default)


def add_log(line: str) -> None:
    with LOCK:
        STATE["log"].append(f"{time.strftime('%H:%M:%S')} {line}")
        if len(STATE["log"]) > 200:
            del STATE["log"][:100]


def snapshot() -> dict:
    with LOCK:
        d = dict(STATE)
        d["captcha_png_seq"] = CAPTCHA["seq"]
        d["vp_png_seq"] = VIEWPORT["seq"]
        return d


# ------------------------------------------------------------------ 页面工具

CAPTCHA_SELECTORS = [
    '[class*="sm-captcha"]',
    "#sm-captcha",
    ".sm-captcha-wrap",
    '[id*="sm-captcha"]',
    'iframe[src*="captcha"]',
    'iframe[src*="shumei"]',
    '[class*="captcha"]',
    '[id*="captcha"]',
]

CODE_SELECTORS = [
    'input[placeholder*="验证码"]',
    'input[placeholder*="邮箱验证码"]',
    'input[name*="code"]',
    'input[maxlength="6"]',
]

EMAIL_SEL = "input[placeholder*='手机号/邮箱']"
PWD_SEL = "input[type=password]"


def js_click_by_text(page, texts, exact=False) -> bool:
    """按按钮文字点击。DeepSeek 前端按钮结构多变，文本匹配最稳。"""
    try:
        return bool(page.evaluate(
            """([texts, exact]) => {
                const norm = s => (s || '').replace(/\\s+/g, '');
                const nodes = document.querySelectorAll(
                    'button, .ds-button__content, a, div[role=button]');
                for (const el of nodes) {
                    const t = norm(el.textContent);
                    if (!t || t.length > 12) continue;
                    const hit = exact ? texts.includes(t)
                                      : texts.some(x => t.includes(x));
                    if (hit) {
                        const btn = el.closest('button') || el;
                        btn.click();
                        return true;
                    }
                }
                return false;
            }""",
            [list(texts), exact]))
    except Exception:  # noqa: BLE001
        return False


def _iter_frames(page):
    """主 frame 优先，再遍历子 frame（数美有时把验证码放 iframe 里）。"""
    try:
        yield page.main_frame
        for fr in page.frames:
            if fr != page.main_frame:
                yield fr
    except Exception:  # noqa: BLE001
        pass


def find_visible(page, selectors, min_w=80, min_h=40, max_w=1200, max_h=900):
    for fr in _iter_frames(page):
        for sel in selectors:
            try:
                els = fr.query_selector_all(sel)
            except Exception:  # noqa: BLE001
                continue
            for el in els:
                try:
                    if not el.is_visible():
                        continue
                    box = el.bounding_box()
                    if not box:
                        continue
                    w, h = box["width"], box["height"]
                    if w < min_w or h < min_h or w > max_w or h > max_h:
                        continue
                    return el, box
                except Exception:  # noqa: BLE001
                    continue
    return None, None


def find_captcha(page):
    return find_visible(page, CAPTCHA_SELECTORS, min_w=140, min_h=90)


def find_code_input(page):
    return find_visible(page, CODE_SELECTORS, min_w=60, min_h=20)


def read_auth(page) -> dict:
    return page.evaluate("""() => {
        const ls = {};
        for (let i = 0; i < localStorage.length; i++) {
            const k = localStorage.key(i);
            ls[k] = localStorage.getItem(k);
        }
        return {
            userToken: ls['userToken'] || null,
            userInfo: ls['__appKit_userInfo'] || null,
            settingsJwt: ls['settingsJwt'] || null,
            deviceId: ls['deepseek-device-id:chat'] || null,
            thumb: Object.entries(ls).find(([k]) => k.startsWith('.thumbcache_'))?.[1] || null,
            smid: ls['smidV2'] || null,
        };
    }""")


def parse_token(raw):
    if not raw:
        return None
    try:
        v = json.loads(raw).get("value")
    except Exception:  # noqa: BLE001
        return None
    if isinstance(v, str) and v:
        return v
    if isinstance(v, dict):
        return v.get("token") or v.get("value")
    return None


# ------------------------------------------------------------------ 浏览器会话

class BrowserSession:
    def __init__(self, headless: bool, visible: bool) -> None:
        self.headless = headless
        self.visible = visible
        self.pw = None
        self.browser = None
        self.ctx = None
        self.page = None
        self.dead = False
        self.last_shot = 0.0
        self.last_vp = 0.0
        self.captcha_box = None
        self.diag_done = False

    # ---- 启动
    def start(self) -> None:
        from playwright.sync_api import sync_playwright

        args = ["--disable-blink-features=AutomationControlled", "--no-first-run"]
        if not self.visible and not self.headless:
            # 窗口挪到屏幕外：用户看不到浏览器，但渲染仍是真实有头模式
            args += ["--window-position=-2400,-2400", "--window-size=1280,900"]

        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(
            headless=self.headless,
            executable_path=str(CHROME) if CHROME.exists() else None,
            args=args,
        )
        self.ctx = self.browser.new_context(
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            viewport={"width": VW, "height": VH},
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/156.0.0.0 Safari/537.36"),
        )
        self.ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        self.page = self.ctx.new_page()
        self.page.goto(SIGN_IN, wait_until="domcontentloaded", timeout=60000)
        add_log("浏览器就绪，登录页已打开")

    # ---- 截图
    def shoot_captcha(self, el, box, force=False) -> None:
        now = time.time()
        if not force and now - self.last_shot < 1.5:
            return
        # 向外扩一圈再截：数美的「确认」按钮常在点选图外侧，
        # 只截面板本体的话用户根本点不到确认，验证永远过不去。
        pad = 90
        cx = max(0, box["x"] - pad)
        cy = max(0, box["y"] - pad)
        cw = min(VW - cx, box["width"] + pad * 2)
        ch = min(VH - cy, box["height"] + pad * 2)
        clip = {"x": cx, "y": cy, "width": cw, "height": ch}
        try:
            png = self.page.screenshot(clip=clip, type="png")
        except Exception:  # noqa: BLE001
            try:
                png = el.screenshot(type="png")
                clip = box
            except Exception:  # noqa: BLE001
                return
        CAPTCHA["seq"] += 1
        CAPTCHA["png"] = png
        self.last_shot = now
        self.captcha_box = clip
        set_state(captcha_seq=CAPTCHA["seq"],
                  captcha_w=int(clip["width"]), captcha_h=int(clip["height"]),
                  has_captcha=True)
        if not self.diag_done:
            self.diag_done = True
            self._log_captcha_diag()

    def _log_captcha_diag(self) -> None:
        """把页面上可见的按钮位置记进日志，方便判断「确认」在哪。"""
        try:
            info = self.page.evaluate("""() => {
                const out = [];
                document.querySelectorAll('button, .ds-button__content, [role=button]')
                  .forEach(b => {
                    const r = b.getBoundingClientRect();
                    if (r.width < 10 || r.height < 8) return;
                    const t = (b.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 14);
                    if (!t) return;
                    out.push(t + '@' + Math.round(r.x + r.width / 2) + ','
                                 + Math.round(r.y + r.height / 2));
                  });
                return out.slice(0, 12);
            }""")
            if info:
                add_log("页面按钮：" + " | ".join(info))
        except Exception:  # noqa: BLE001
            pass

    def shoot_viewport(self, force=False) -> None:
        now = time.time()
        if not force and now - self.last_vp < 1.2:
            return
        try:
            png = self.page.screenshot(type="png")
        except Exception:  # noqa: BLE001
            return
        VIEWPORT["seq"] += 1
        VIEWPORT["png"] = png
        self.last_vp = now
        set_state(vp_seq=VIEWPORT["seq"])

    # ---- 轮询
    def tick(self) -> None:
        page = self.page
        if page is None or page.is_closed():
            return
        try:
            url = page.url
            snap = read_auth(page)
        except Exception:  # noqa: BLE001  页面跳转中
            return

        if get_state("url") != url:
            set_state(url=url)
            add_log(f"页面：{url}")

        token = parse_token(snap.get("userToken"))
        if token:
            self.finish(token, snap)
            return

        # 1) 验证码优先
        el, box = find_captcha(page)
        if el is not None:
            self.shoot_captcha(el, box)
            if get_state("stage") != "captcha":
                set_state(stage="captcha",
                          message="请点击图中要求的图形 —— 直接在这个页面上点")
                add_log("检测到人机验证，已把验证码显示到页面")
            return

        # 2) 邮箱验证码输入框（只在登录过程中判断，避免初始 tab 误判）
        stage = get_state("stage")
        if stage in ("submitting", "mfa_code"):
            code_el, _ = find_code_input(page)
            if code_el is not None:
                if stage != "mfa_code":
                    set_state(stage="mfa_code", has_captcha=False,
                              message="已进入邮箱验证：先点「发送验证码」，收到后填进来")
                    add_log("进入 MFA 邮箱验证阶段")
                return

        # 3) 错误提示
        try:
            txt = page.inner_text("body")[:3000]
        except Exception:  # noqa: BLE001
            txt = ""
        for kw in ("密码错误", "账号或密码", "验证码错误", "验证码已过期",
                   "验证码不正确", "操作过于频繁", "账号不存在", "该账号"):
            if kw in txt:
                if get_state("stage") not in ("done", "error"):
                    set_state(stage="error", error=kw, message=f"登录失败：{kw}")
                    add_log(f"页面提示：{kw}")
                return

    # ---- 完成
    def finish(self, token: str, snap: dict) -> None:
        if get_state("stage") == "done":
            return
        set_state(stage="done", has_captcha=False, message="登录成功，token 已加密保存")
        add_log("捕获到 userToken")
        try:
            from token_store import TokenStore, token_state

            thumb = snap.get("thumb") or ""
            device_id = ("B" + thumb) if thumb else None
            store = TokenStore()
            store.save_state(self.ctx.storage_state())
            path = store.save({
                "token": token,
                "device_id": device_id,
                "smid": thumb,
                "smidV2": snap.get("smid"),
                "uuid_device_id": snap.get("deviceId"),
                "user_info": snap.get("userInfo"),
                "settings_jwt": snap.get("settingsJwt"),
                "saved_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            })
            st = token_state(token)
            set_state(token_info={
                "path": str(path),
                "token_len": len(token),
                "token_head": token[:24] + "…",
                "expires_at": st.get("expires_at"),
                "remain_s": st.get("remain_s"),
                "device_id": (device_id or "")[:32],
            })
            add_log(f"token 已保存：{path}")
        except Exception as exc:  # noqa: BLE001
            add_log(f"保存 token 失败：{exc}")
            set_state(error=str(exc))

    # ---- 命令
    def do_login(self, email: str, password: str) -> None:
        page = self.page
        set_state(stage="submitting", message="正在切换到密码登录…", error=None)
        if js_click_by_text(page, ["密码登录"], exact=True):
            add_log("已切到「密码登录」")
        page.wait_for_timeout(2000)

        try:
            page.fill(EMAIL_SEL, email, timeout=15000)
            page.fill(PWD_SEL, password, timeout=15000)
        except Exception as exc:  # noqa: BLE001
            set_state(stage="error", error=str(exc),
                      message="没找到账号/密码输入框，请用「整页视图」看看后台页面")
            add_log(f"填表失败：{exc}")
            return

        add_log("账号密码已填入，提交登录")
        js_click_by_text(page, ["登录"], exact=True)
        set_state(message="已提交，等待结果（出现验证码会显示在本页）")

    def do_send_code(self) -> None:
        if js_click_by_text(self.page, ["发送验证码"], exact=True):
            add_log("已点「发送验证码」，等验证码弹出")
            set_state(message="已请求发送验证码…")
        else:
            add_log("没找到「发送验证码」按钮")
            set_state(message="没找到「发送验证码」按钮（可能已发送过）")

    def do_submit_code(self, code: str) -> None:
        el, _ = find_code_input(self.page)
        if el is None:
            set_state(message="没找到验证码输入框")
            return
        try:
            el.fill(code)
        except Exception:  # noqa: BLE001
            el.click()
            self.page.keyboard.type(code, delay=60)
        add_log(f"验证码已填入（{len(code)} 位），提交")
        js_click_by_text(self.page, ["验证并登录", "登录", "确定", "提交"])
        set_state(message="已提交验证码，等待登录结果")

    def _human_click(self, x: float, y: float) -> None:
        """分步移动 + 短按：避免「瞬移点击」被数美判成脚本行为。"""
        import random

        self.page.mouse.move(x, y, steps=random.randint(6, 12))
        self.page.wait_for_timeout(random.randint(70, 150))
        self.page.mouse.down()
        self.page.wait_for_timeout(random.randint(40, 110))
        self.page.mouse.up()

    def do_click_captcha(self, rx: float, ry: float) -> None:
        box = self.captcha_box
        if not box:
            set_state(message="验证码位置失效，正在重新获取")
            return
        x = box["x"] + rx * box["width"]
        y = box["y"] + ry * box["height"]
        try:
            self._human_click(x, y)
            add_log(f"点击验证码 ({rx:.2f}, {ry:.2f})")
        except Exception as exc:  # noqa: BLE001
            add_log(f"点击失败：{exc}")
        self.page.wait_for_timeout(800)
        el, b = find_captcha(self.page)
        if el is not None:
            self.shoot_captcha(el, b, force=True)

    def do_click_viewport(self, rx: float, ry: float) -> None:
        x = rx * VW
        y = ry * VH
        try:
            self._human_click(x, y)
            add_log(f"整页点击 ({x:.0f}, {y:.0f})")
        except Exception as exc:  # noqa: BLE001
            add_log(f"整页点击失败：{exc}")
        self.page.wait_for_timeout(700)
        self.shoot_viewport(force=True)

    def do_reload(self) -> None:
        self.page.goto(SIGN_IN, wait_until="domcontentloaded", timeout=60000)
        set_state(stage="idle", message="已重置，请重新输入账号密码",
                  has_captcha=False, token_info=None, error=None)
        add_log("页面已重置")

    # ---- 主循环
    def run(self) -> None:
        while not self.dead:
            try:
                cmd = CMDS.get(timeout=0.6)
            except queue.Empty:
                cmd = None

            if cmd is not None:
                name, payload = cmd
                if name == "quit":
                    break
                try:
                    if name == "login":
                        self.do_login(payload["email"], payload["password"])
                    elif name == "send_code":
                        self.do_send_code()
                    elif name == "submit_code":
                        self.do_submit_code(payload["code"])
                    elif name == "click":
                        self.do_click_captcha(payload["rx"], payload["ry"])
                    elif name == "vpclick":
                        self.do_click_viewport(payload["rx"], payload["ry"])
                    elif name == "vp_shot":
                        self.shoot_viewport(force=True)
                    elif name == "reload":
                        self.do_reload()
                except Exception as exc:  # noqa: BLE001
                    add_log(f"命令 {name} 出错：{exc}")

            try:
                self.tick()
                # 处于需要人工干预的阶段时持续刷新整页视图
                if get_state("stage") in ("captcha", "mfa_code", "submitting"):
                    self.shoot_viewport()
            except Exception as exc:  # noqa: BLE001
                add_log(f"轮询出错：{exc}")

        self.shutdown()

    def shutdown(self) -> None:
        for obj, meth in ((self.ctx, "close"), (self.browser, "close"),
                          (self.pw, "stop")):
            try:
                if obj is not None:
                    getattr(obj, meth)()
            except Exception:  # noqa: BLE001
                pass


# ------------------------------------------------------------------ 前端

HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>DeepSeek 登录</title>
<style>
  *{box-sizing:border-box}
  body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
    padding:24px;background:radial-gradient(1200px 600px at 50% -10%,#1b2a4a 0%,#0b0f17 55%);
    color:#e6edf7;font:14px/1.6 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
  .card{width:100%;max-width:440px;background:rgba(20,27,40,.92);border:1px solid #24304a;
    border-radius:16px;padding:26px 24px;box-shadow:0 24px 64px rgba(0,0,0,.5)}
  h1{margin:0 0 4px;font-size:19px;font-weight:600}
  .sub{color:#7d8ba6;font-size:12px;margin-bottom:18px}
  label{display:block;font-size:12px;color:#93a2bd;margin:13px 0 6px}
  input{width:100%;padding:11px 13px;border-radius:9px;border:1px solid #2b3a58;
    background:#0e1523;color:#e6edf7;font-size:14px;outline:none;transition:border-color .15s}
  input:focus{border-color:#4b7bec}
  button{width:100%;padding:12px;margin-top:15px;border:0;border-radius:9px;
    background:linear-gradient(180deg,#4b7bec,#3a63cc);color:#fff;font-size:14px;
    font-weight:600;cursor:pointer;transition:opacity .15s}
  button:disabled{opacity:.45;cursor:not-allowed}
  button.ghost{background:#1a2436;border:1px solid #2b3a58;color:#a9b8d2;
    font-weight:500;margin-top:9px;padding:9px;font-size:13px}
  .row{display:flex;gap:9px}
  .row>*{flex:1}
  .msg{margin:15px 0 0;padding:11px 13px;border-radius:9px;background:#101a2b;
    border:1px solid #22314c;color:#9fb0cd;font-size:13px}
  .msg.err{background:#2a1417;border-color:#5c2530;color:#ff9aa6}
  .msg.ok{background:#10281c;border-color:#235c3c;color:#7ee2a8}
  .stage{margin-top:15px;text-align:center;display:none}
  .stage img{max-width:100%;border-radius:10px;border:1px solid #33456a;display:block;
    margin:0 auto;cursor:crosshair;transition:opacity .12s}
  .hint{font-size:12px;color:#7d8ba6;margin-top:8px}
  .tabs{display:flex;gap:8px;margin-top:14px}
  .tabs button{margin-top:0;padding:8px;font-size:12px;font-weight:500;background:#141c2c;
    border:1px solid #24304a;color:#8fa1bd}
  .tabs button.on{background:#20304d;border-color:#3d5c8f;color:#cfe0ff}
  pre.log{margin:14px 0 0;padding:10px 12px;max-height:120px;overflow:auto;background:#0a1019;
    border:1px solid #1b2538;border-radius:8px;font:11px/1.55 ui-monospace,Consolas,monospace;
    color:#6b7c99;white-space:pre-wrap;word-break:break-all}
  .kv{font-size:12px;color:#93a2bd;margin-top:10px;word-break:break-all;line-height:1.85}
  .kv b{color:#cfe0ff;font-weight:500}
  .hidden{display:none!important}
  .url{font:11px ui-monospace,Consolas,monospace;color:#5d6f8d;margin-top:10px;
    word-break:break-all}
  .card.wide{max-width:1040px}
  .stage img{width:100%;height:auto}
  #zoom{position:fixed;inset:0;z-index:999;background:rgba(4,7,12,.95);
    display:none;flex-direction:column;align-items:center;justify-content:center;padding:14px}
  #zoom.on{display:flex}
  #zoom img{max-width:96vw;max-height:84vh;width:auto;border-radius:8px;
    border:1px solid #33456a;cursor:crosshair;box-shadow:0 20px 60px rgba(0,0,0,.7)}
  #zoom .ztip{color:#9fb0cd;font-size:12px;margin-top:12px;text-align:center;line-height:1.7}
  #zoom .zclose{position:absolute;top:14px;right:18px;width:auto;margin:0;padding:6px 14px;
    font-size:12px;background:#1a2436;border:1px solid #2b3a58;color:#a9b8d2}
</style>
</head>
<body>
<div class="card">
  <h1>DeepSeek 登录</h1>
  <div class="sub">账号密码在本机提交；触发验证码时直接显示在这里</div>

  <div id="form">
    <label>账号（手机号 / 邮箱）</label>
    <input id="email" autocomplete="username" placeholder="you@example.com">
    <label>密码</label>
    <input id="password" type="password" autocomplete="current-password" placeholder="••••••••">
    <button id="btnLogin">登录</button>
  </div>

  <div id="flow" class="hidden">
    <div id="msg" class="msg"></div>

    <!-- 验证码视图 -->
    <div id="capWrap" class="stage">
      <img id="capImg" alt="人机验证">
      <div class="hint">在图上点出要求的位置；点错会自动换一张</div>
    </div>

    <!-- 整页视图 -->
    <div id="vpWrap" class="stage">
      <img id="vpImg" alt="页面">
      <div class="hint">这是后台浏览器的真实画面，点哪里就点哪里</div>
    </div>

    <div class="tabs" id="tabs">
      <button id="tabCap">验证码</button>
      <button id="tabVp">整页视图</button>
    </div>

    <div id="mfaWrap" class="hidden">
      <label>邮箱验证码</label>
      <input id="code" inputmode="numeric" maxlength="8" placeholder="6 位数字">
      <div class="row">
        <button id="btnSend" class="ghost">发送验证码</button>
        <button id="btnSubmit" class="ghost">提交</button>
      </div>
    </div>

    <div id="doneWrap" class="hidden">
      <div id="tokenKv" class="kv"></div>
    </div>

    <div class="url" id="urlLine"></div>
    <button id="btnReset" class="ghost">重新开始</button>
  </div>

  <pre id="log" class="log hidden"></pre>
</div>

<div id="zoom">
  <button id="zoomClose" class="zclose">关闭 (Esc)</button>
  <img id="zoomImg" alt="放大视图">
  <div class="ztip" id="zoomTip"></div>
</div>

<script>
const $ = id => document.getElementById(id);
let capSeq = -1, vpSeq = -1, polling = false, view = 'cap';
let lastStage = '', zoomMode = null;
const show = (el, on) => el.classList.toggle('hidden', !on);

function setView(v) {
  view = v;
  $('tabCap').classList.toggle('on', v === 'cap');
  $('tabVp').classList.toggle('on', v === 'vp');
  $('capWrap').style.display = (v === 'cap' && !$('capWrap').classList.contains('hidden')) ? 'block' : 'none';
  $('vpWrap').style.display = (v === 'vp' && !$('vpWrap').classList.contains('hidden')) ? 'block' : 'none';
}

function render(s) {
  const idle = s.stage === 'idle';
  show($('form'), idle);
  show($('flow'), !idle);
  show($('log'), !!(s.log && s.log.length));
  if (s.log) $('log').textContent = s.log.slice(-40).join('\n');
  if (s.url) $('urlLine').textContent = s.url;

  const m = $('msg');
  m.textContent = s.message || '';
  m.className = 'msg' + (s.stage === 'error' ? ' err' : (s.stage === 'done' ? ' ok' : ''));

  const capOn = s.stage === 'captcha';
  const vpOn = !idle && s.stage !== 'done';
  const wasCap = lastStage === 'captcha';
  lastStage = s.stage;
  document.querySelector('.card').classList.toggle('wide', capOn || vpOn);
  show($('capWrap'), capOn);
  show($('vpWrap'), vpOn);
  show($('tabs'), capOn || vpOn);

  if (capOn && s.captcha_seq !== capSeq) {
    capSeq = s.captcha_seq;
    $('capImg').src = '/api/captcha.png?seq=' + capSeq;
  }
  // 刚进入验证码阶段就自动放大，省得用户在小图上瞎点
  if (capOn && !wasCap && !zoomMode) setTimeout(() => openZoom('cap'), 450);
  if (vpOn && s.vp_seq !== vpSeq) {
    vpSeq = s.vp_seq;
    $('vpImg').src = '/api/view.png?seq=' + vpSeq;
  }
  // 没检测到验证码时自动落到整页视图
  if (!capOn && view === 'cap') setView('vp');
  if (capOn && view === 'vp') { /* 保留用户选择 */ }
  setView(view);

  show($('mfaWrap'), s.stage === 'mfa_code');
  show($('doneWrap'), s.stage === 'done');
  if (s.stage === 'done' && s.token_info) {
    const t = s.token_info;
    $('tokenKv').innerHTML =
      '已保存：<b>' + t.path + '</b><br>' +
      'token：<b>' + t.token_head + '</b>（' + t.token_len + ' 字符）<br>' +
      '过期：<b>' + (t.expires_at || '未知') + '</b>' +
      (t.remain_s != null ? '（剩余 ' + Math.round(t.remain_s / 60) + ' 分钟）' : '');
  }

  const working = ['starting', 'submitting'].includes(s.stage);
  $('btnLogin').disabled = s.busy || working;
  $('btnReset').disabled = working;
}

async function poll() {
  if (polling) return;
  polling = true;
  try {
    const r = await fetch('/api/state');
    render(await r.json());
  } catch (e) {}
  polling = false;
}

const post = (url, body) => fetch(url, {
  method: 'POST', headers: {'Content-Type': 'application/json'},
  body: JSON.stringify(body || {})
}).then(r => r.json());

$('btnLogin').onclick = async () => {
  const email = $('email').value.trim();
  const password = $('password').value;
  if (!email || !password) { alert('账号和密码都要填'); return; }
  $('btnLogin').disabled = true;
  await post('/api/login', {email, password});
  $('password').value = '';
  poll();
};

function openZoom(mode) {
  zoomMode = mode;
  const src = mode === 'cap' ? $('capImg').src : $('vpImg').src;
  if (!src || src.indexOf('/api/') < 0) return;
  $('zoomImg').src = src;
  $('zoomTip').textContent = mode === 'cap'
    ? '直接在大图上点出要求的位置（点错会自动换一张）；看不到「确认」按钮就关掉切「整页视图」'
    : '这是后台浏览器的真实画面，点哪里就点哪里';
  $('zoom').classList.add('on');
}
function closeZoom() {
  $('zoom').classList.remove('on');
  zoomMode = null;
}
$('zoomClose').onclick = closeZoom;
$('zoom').onclick = ev => { if (ev.target === $('zoom')) closeZoom(); };
document.addEventListener('keydown', ev => { if (ev.key === 'Escape') closeZoom(); });

$('zoomImg').onclick = async ev => {
  if (!zoomMode) return;
  const img = ev.currentTarget, rect = img.getBoundingClientRect();
  const rx = (ev.clientX - rect.left) / rect.width;
  const ry = (ev.clientY - rect.top) / rect.height;
  if (rx < 0 || rx > 1 || ry < 0 || ry > 1) return;
  const mode = zoomMode;
  img.style.opacity = '.5';
  await post(mode === 'cap' ? '/api/click' : '/api/vpclick', {rx, ry});
  img.style.opacity = '1';
  setTimeout(() => { if (mode === 'cap') closeZoom(); poll(); }, 400);
  poll();
};

$('capImg').onclick = () => openZoom('cap');
$('vpImg').onclick = () => openZoom('vp');

$('tabCap').onclick = () => setView('cap');
$('tabVp').onclick = () => { setView('vp'); post('/api/vp_shot'); };
$('btnSend').onclick = async () => { await post('/api/send_code'); poll(); };
$('btnSubmit').onclick = async () => {
  const code = $('code').value.trim();
  if (!code) { alert('先填验证码'); return; }
  await post('/api/submit_code', {code});
  $('code').value = '';
  poll();
};
$('btnReset').onclick = async () => { await post('/api/reset'); poll(); };

setInterval(poll, 700);
poll();
</script>
</body>
</html>
"""


# ------------------------------------------------------------------ HTTP

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args) -> None:
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except Exception:  # noqa: BLE001
            pass

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send(200, HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/api/state":
            self._send(200, json.dumps(snapshot(), ensure_ascii=False).encode(),
                       "application/json; charset=utf-8")
        elif path == "/api/captcha.png":
            if CAPTCHA["png"]:
                self._send(200, CAPTCHA["png"], "image/png")
            else:
                self._send(404, b"no captcha", "text/plain")
        elif path == "/api/view.png":
            if VIEWPORT["png"]:
                self._send(200, VIEWPORT["png"], "image/png")
            else:
                self._send(404, b"no view", "text/plain")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            n = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(n) or b"{}")
        except Exception:  # noqa: BLE001
            payload = {}

        if path == "/api/login":
            email = (payload.get("email") or "").strip()
            password = payload.get("password") or ""
            if not email or not password:
                self._send(400, b'{"ok":false,"error":"missing"}',
                           "application/json")
                return
            set_state(stage="starting", message="正在启动浏览器…", error=None,
                      log=[], has_captcha=False, token_info=None, busy=True)
            add_log("收到登录请求")
            START_EVENT.set()
            CMDS.put(("login", {"email": email, "password": password}))
            threading.Thread(target=_clear_busy, daemon=True).start()
        elif path == "/api/click":
            CMDS.put(("click", {"rx": float(payload.get("rx", 0)),
                                "ry": float(payload.get("ry", 0))}))
        elif path == "/api/vpclick":
            CMDS.put(("vpclick", {"rx": float(payload.get("rx", 0)),
                                  "ry": float(payload.get("ry", 0))}))
        elif path == "/api/vp_shot":
            CMDS.put(("vp_shot", {}))
        elif path == "/api/send_code":
            CMDS.put(("send_code", {}))
        elif path == "/api/submit_code":
            CMDS.put(("submit_code", {"code": str(payload.get("code", ""))}))
        elif path == "/api/reset":
            set_state(stage="starting", message="正在重置…", has_captcha=False,
                      token_info=None, error=None, busy=True)
            CMDS.put(("reload", {}))
            threading.Thread(target=_clear_busy, daemon=True).start()
        else:
            self._send(404, b"not found", "text/plain")
            return

        self._send(200, b'{"ok":true}', "application/json")


def _clear_busy() -> None:
    time.sleep(1.5)
    set_state(busy=False)


# ------------------------------------------------------------------ 启动

def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--visible", action="store_true", help="显示后台浏览器窗口")
    ap.add_argument("--headless", action="store_true", help="无头模式（调试用）")
    args = ap.parse_args()

    WORK.mkdir(parents=True, exist_ok=True)
    add_log("本地登录页已启动")

    session = BrowserSession(headless=args.headless, visible=args.visible)

    def browser_thread() -> None:
        """浏览器线程：start() 与 run() 同线程顺序执行。"""
        START_EVENT.wait()
        try:
            session.start()
            session.run()
        except Exception as exc:  # noqa: BLE001
            set_state(stage="error", error=str(exc),
                      message=f"浏览器线程异常：{exc}")
            add_log(traceback.format_exc(limit=3))

    threading.Thread(target=browser_thread, daemon=True).start()

    url = f"http://127.0.0.1:{args.port}/"
    print("=" * 64)
    print(f"  登录页面已启动： {url}")
    print(f"  浏览器窗口： {'可见' if args.visible else '已移到屏幕外（不打扰）'}")
    print("  Ctrl+C 退出")
    print("=" * 64)

    try:
        srv = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    except OSError as exc:
        print(f"[错误] 端口 {args.port} 启动失败：{exc}")
        print(f"       换端口重试： --port {args.port + 1}")
        return

    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n退出中…")
    finally:
        session.dead = True
        CMDS.put(("quit", {}))
        time.sleep(0.3)
        srv.server_close()


if __name__ == "__main__":
    main()
