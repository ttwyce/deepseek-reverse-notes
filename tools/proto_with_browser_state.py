# -*- coding: utf-8 -*-
"""用浏览器导出的 storage_state（全量 cookie）+ 同一 device_id，纯协议重试登录。

目的：确认纯协议能否拿到 biz_code 14 + mfa_session_id（而不是 11）。
"""
from __future__ import annotations
# --- credentials: 从环境变量或本地 local_config.py 读取（local_config 不入库）---
import os as _os


def _cred(key, default=""):
    v = _os.environ.get(key)
    if v:
        return v
    try:
        from local_config import CFG  # type: ignore
        return CFG.get(key, default)
    except Exception:
        return default



import json
import sys

import requests

sys.path.insert(0, r"F:\dshh\deepseeka\tools")
from deepseek_client import DeepSeekClient  # noqa: E402

WORK = r"F:\dshh\deepseeka\work"
EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")


def load_state():
    with open(WORK + r"\pw_pwd_state.json", "r", encoding="utf-8") as fh:
        return json.load(fh)


def main() -> None:
    state = load_state()
    cookies = {c["name"]: c["value"] for c in state.get("cookies", [])}
    print("cookies:", list(cookies.keys()))

    # 从 localStorage 取 device_id
    device_id = None
    for item in state.get("origins", []):
        for kv in item.get("localStorage", []):
            if kv["name"] == "deepseek-device-id:chat":
                device_id = kv["value"]
    print("device_id:", device_id)

    for os_name in ("web", "android"):
        cli = DeepSeekClient(device_id=device_id, os_name=os_name)
        cli.session.cookies.update(cookies)
        body = {"email": EMAIL, "password": PASSWORD,
                "device_id": device_id, "os": os_name}
        if os_name == "web":
            body["credential_id"] = ""
        r = cli.session.post("https://chat.deepseek.com/api/v0/users/login",
                       json=body, headers=cli.headers(), timeout=30)
        print(f"\n--- os={os_name} status={r.status_code}")
        print(r.text[:600])


if __name__ == "__main__":
    main()
