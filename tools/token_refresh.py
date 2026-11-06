# -*- coding: utf-8 -*-
"""token 静默续期：用已保存的 storage_state 起一个无头浏览器，
让 DeepSeek 前端自己走它原有的续期逻辑，再把新 token 取回来。

前提：work\\pw_auth_state.enc 存在（由 tools\\pw_get_token.py 首次人工授权时保存）。
不需要人工参与；若 refresh 凭证也已失效，会明确提示重新人工授权一次。

用法：
    python tools\\token_refresh.py            # 续期并保存
    python tools\\token_refresh.py --check    # 只看当前 token 状态，不启动浏览器
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(r"F:\dshh\deepseeka")
WORK = ROOT / "work"
CHROME = ROOT / "tools" / "pw-browsers" / "chromium-1248" / "chrome-win64" / "chrome.exe"
BASE = "https://chat.deepseek.com"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from token_store import TokenStore, jwt_exp, token_state  # noqa: E402

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36")

# 页面内读认证快照（与 pw_get_token.py 保持一致）
_READ_JS = """() => {
    const ls = {};
    for (let i = 0; i < localStorage.length; i++) {
        const k = localStorage.key(i);
        ls[k] = localStorage.getItem(k);
    }
    const pick = Object.entries(ls).find(([k]) => k.startsWith('.thumbcache_'));
    return {
        userToken: ls['userToken'] || null,
        userInfo: ls['__appKit_userInfo'] || null,
        settingsJwt: ls['settingsJwt'] || null,
        deviceId: ls['deepseek-device-id:chat'] || null,
        thumb: pick ? pick[1] : null,
        smid: ls['smidV2'] || null,
    };
}"""


def _parse_token(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        v = json.loads(raw).get("value")
    except Exception:  # noqa: BLE001
        return None
    if isinstance(v, str):
        return v or None
    if isinstance(v, dict):
        return v.get("token") or v.get("value") or None
    return None


def refresh(verbose: bool = True, wait_s: int = 45) -> dict | None:
    """返回 {'token': str, 'changed': bool, 'snapshot': dict} 或 None。"""
    from playwright.sync_api import sync_playwright

    store = TokenStore()
    state = store.load_state()
    if not state:
        if verbose:
            print("[refresh] 没有 storage_state，无法静默续期")
        return None

    old_token = None
    if store.exists():
        try:
            old_token = store.load().get("token")
        except SystemExit:
            old_token = None

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True, executable_path=str(CHROME),
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = browser.new_context(
            storage_state=state,
            locale="zh-CN", timezone_id="Asia/Shanghai",
            user_agent=UA,
        )
        ctx.add_init_script(
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = ctx.new_page()
        try:
            page.goto(BASE, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:  # noqa: BLE001
            if verbose:
                print("[refresh] 打开页面失败:", e)
            browser.close()
            return None

        # 前端会拿 cookie 里的 refresh 凭证自动换新 token，给它一点时间
        snap: dict = {}
        token: str | None = None
        deadline = time.time() + wait_s
        while time.time() < deadline:
            page.wait_for_timeout(1500)
            try:
                snap = page.evaluate(_READ_JS)
            except Exception:  # noqa: BLE001
                continue
            token = _parse_token(snap.get("userToken"))
            if token and (jwt_exp(token) or 0) > time.time():
                break
            token = None

        if not token:
            if verbose:
                print("[refresh] 未拿到有效 token —— refresh 凭证可能也已失效，"
                      "需要重新运行 tools\\pw_get_token.py 人工授权一次")
            browser.close()
            return None

        # 保存新 token + 刷新后的 storage_state
        thumb = snap.get("thumb") or ""
        payload = {
            "token": token,
            "device_id": ("B" + thumb) if thumb else None,
            "smid": thumb,
            "smidV2": snap.get("smid"),
            "uuid_device_id": snap.get("deviceId"),
            "user_info": snap.get("userInfo"),
            "settings_jwt": snap.get("settingsJwt"),
            "refreshed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        if store.exists():  # 保留原有元信息
            try:
                payload = {**store.load(), **{k: v for k, v in payload.items()
                                              if v is not None}}
            except SystemExit:
                pass
        store.save(payload)
        store.save_state(ctx.storage_state())
        browser.close()

    changed = bool(old_token) and token != old_token
    if verbose:
        st = token_state(token)
        print(f"[refresh] 续期成功，{'token 已更新' if changed else 'token 未变'}")
        print("  过期时间:", st.get("expires_at"))
    return {"token": token, "changed": changed, "snapshot": snap}


def main() -> None:
    store = TokenStore()
    if "--check" in sys.argv:
        if not store.exists():
            print("[未授权] 无 token")
            return
        info = store.load()
        st = token_state(info.get("token") or "")
        print(json.dumps({"saved_at": info.get("saved_at"),
                          "token_state": st,
                          "has_storage_state": store.has_state()},
                         ensure_ascii=False, indent=2))
        return
    r = refresh()
    if not r:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
