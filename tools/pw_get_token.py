# -*- coding: utf-8 -*-
"""半自动取 token：开可见浏览器 → 用户手动完成 MFA（滑块 + 邮箱验证码）
→ 脚本自动捕获 userToken / storage_state 并落盘，供后续纯协议调用。

用法：
    .\\.venv\\Scripts\\python.exe tools\\pw_get_token.py

产出（均为 Windows DPAPI 加密，绑定当前用户）：
    work\\auth_token.enc      { token, device_id, smid, saved_at, ... }
    work\\pw_auth_state.enc   Playwright storage_state（cookie + localStorage）

之后可用 tools\\token_refresh.py 无人工静默续期。

说明：
    DeepSeek 账号已开启 MFA（biz_code 14），发码环节是数美滑块验证码，
    纯协议无法通过（需真人视觉点选）。因此授权环节用真实浏览器过一次，
    之后所有 /api/v0/* 调用都可用 Authorization: Bearer <token> 纯协议完成。
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(r"F:\dshh\deepseeka")
WORK = ROOT / "work"
CHROME = ROOT / "tools" / "pw-browsers" / "chromium-1248" / "chrome-win64" / "chrome.exe"

sys_path_root = str(ROOT / "tools")
import sys as _sys  # noqa: E402

if sys_path_root not in _sys.path:
    _sys.path.insert(0, sys_path_root)
from token_store import TokenStore  # noqa: E402

SIGN_IN = "https://chat.deepseek.com/sign_in"
TIMEOUT_S = 900  # 15 分钟，够过滑块 + 收邮件


def read_auth(page) -> dict:
    """从 localStorage / cookie 读出认证相关快照。"""
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


def parse_token(raw: str | None) -> str | None:
    """userToken 形如 {"value":"<jwt>"} 或 {"value":null}。"""
    if not raw:
        return None
    try:
        v = json.loads(raw).get("value")
    except Exception:  # noqa: BLE001
        return None
    if not v:
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, dict):
        return v.get("token") or v.get("value")
    return None


def main() -> None:
    WORK.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False, executable_path=str(CHROME),
            args=["--disable-blink-features=AutomationControlled",
                  "--start-maximized"],
        )
        ctx = browser.new_context(
            locale="zh-CN", timezone_id="Asia/Shanghai", no_viewport=True,
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/156.0.0.0 Safari/537.36"),
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = ctx.new_page()
        page.goto(SIGN_IN, wait_until="domcontentloaded")

        print("=" * 62)
        print("浏览器已打开，请在窗口内手动完成登录：")
        print("  1) 切「密码登录」，填 <your-email> / 密码，点登录")
        print("  2) MFA 页点「发送验证码」，完成数美滑块/点选")
        print("  3) 到邮箱取验证码，填入后点「验证并登录」")
        print("登录成功后脚本会自动捕获 token，无需其他操作。")
        print("=" * 62)

        deadline = time.time() + TIMEOUT_S
        token = None
        snap: dict = {}
        while time.time() < deadline:
            page.wait_for_timeout(2000)
            try:
                snap = read_auth(page)
            except Exception:  # noqa: BLE001  页面跳转中
                continue
            token = parse_token(snap.get("userToken"))
            if token:
                print("[OK] 捕获到 userToken")
                break
            if page.url.rstrip("/") not in (SIGN_IN, "https://chat.deepseek.com"):
                print("  ... 当前页面:", page.url)

        if not token:
            print("[FAIL] 超时未捕获到 token；浏览器保持打开，可手动重试")
            print("当前快照:", json.dumps(snap, ensure_ascii=False)[:600])
            browser.close()
            return

        thumb = snap.get("thumb") or ""
        device_id = ("B" + thumb) if thumb else None
        store = TokenStore()
        store.save_state(ctx.storage_state())

        payload = {
            "token": token,
            "device_id": device_id,
            "smid": thumb,
            "smidV2": snap.get("smid"),
            "uuid_device_id": snap.get("deviceId"),
            "user_info": snap.get("userInfo"),
            "settings_jwt": snap.get("settingsJwt"),
            "saved_at": datetime.now(timezone.utc).astimezone().isoformat(),
        }
        enc_path = store.save(payload)

        from token_store import token_state
        st = token_state(token)
        print("\n[SAVED] 已加密落盘:", enc_path)
        print("  token 长度 :", len(token))
        print("  device_id  :", (device_id or "")[:32], "...")
        print("  过期时间   :", st.get("expires_at") or "未知（非 JWT）")
        print("  storage    :", store.state_enc)

        # 立刻用纯协议验证 token 是否可用
        print("\n--- 纯协议验证 token ---")
        r = page.request.get(
            "https://chat.deepseek.com/api/v0/users/current",
            headers={"Authorization": f"Bearer {token}",
                     "x-client-platform": "web",
                     "x-client-version": "2.7.0",
                     "x-client-bundle-id": "com.deepseek.chat"},
        )
        print("GET /api/v0/users/current ->", r.status)
        print(r.text()[:600])

        browser.close()


if __name__ == "__main__":
    main()
