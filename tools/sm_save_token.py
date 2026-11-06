# -*- coding: utf-8 -*-
"""把 sm_mfa_check.py 拿到的 token 加密落盘（DPAPI），供 deepseek_api.py 复用。"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

sys.path.insert(0, r"F:\dshh\deepseeka\tools")
from proto_login_full import WORK  # noqa: E402
from token_store import TokenStore, token_state  # noqa: E402


def main() -> None:
    with open(WORK + r"\auth_mfa_result.json", encoding="utf-8") as f:
        res = json.load(f)
    data = (res["raw"].get("data") or {}).get("biz_data") or {}
    user = data.get("user") or {}
    token = user.get("token") or ""
    if not token:
        raise SystemExit("auth_mfa_result.json 里没有 token")

    device_id = res.get("device_id") or ""
    smid = device_id[1:] if device_id.startswith("B") else device_id

    payload = {
        "token": token,
        "device_id": device_id,
        "smid": smid,
        "user_info": user,
        "mfa_ticket": data.get("mfa_ticket"),
        "source": "sm_full_login + shumei_solver",
        "saved_at": datetime.now(timezone.utc).astimezone().isoformat(),
    }
    path = TokenStore().save(payload)
    print("saved:", path)
    print("token len:", len(token))
    print("device_id:", device_id[:24], "...")
    print("token_state:", json.dumps(token_state(token), ensure_ascii=False))
    print("email:", user.get("email"))
    print("uid:", user.get("id"))


if __name__ == "__main__":
    main()
