# -*- coding: utf-8 -*-
"""纯协议发码（照抄 tools/sm_full_login.py 的三步，只把设备号换成纯协议生成）。

与 sm_full_login.py 的唯一差别：
    sm_full_login.py 用 grab_smid()（Playwright 打开首页读 .thumbcache_* cookie）
    本脚本用 tools/sm_fp_client.py 直接请求数美 deviceprofile/v4 换 deviceId
    —— 全程无浏览器。

用法：
    set DS_EMAIL / DS_PASSWORD（或 tools/local_config.py）
    python tools\\sm_login_pure.py

产物：work\\mfa_state.json（device_id / mfa_session_id / rid / email）
下一步：python tools\\sm_submit_code.py <6位验证码>
"""
from __future__ import annotations

import json
import os
import sys
import time

import requests

sys.path.insert(0, r"F:\dshh\deepseeka\tools")
from proto_login_full import BASE, EMAIL, PASSWORD, WORK, enc_post  # noqa: E402
from shumei_solver import solve  # noqa: E402
import sm_fp_client  # noqa: E402
from enc_login_test import base_headers  # noqa: E402

SM_URL = "https://fp-it-acc.portal101.cn/deviceprofile/v4"
TARGET = "/api/v0/users/mfa/create_verification_code"


def shumei_device_id() -> str:
    """向数美换一个服务端登记过的 88 字符 deviceId。"""
    _uid, _pri, body = sm_fp_client.build_request(
        sm_fp_client.build_fields(sm_fp_client.load_template()))
    r = requests.post(SM_URL, json=body, headers=sm_fp_client.HEADERS, timeout=15)
    j = r.json()
    dev = ((j.get("detail") or {}).get("deviceId") or "")
    print(f"[shumei] HTTP {r.status_code} code={j.get('code')} "
          f"requestId={j.get('requestId')} deviceId_len={len(dev)}")
    if j.get("code") != 1100 or len(dev) != 88:
        raise SystemExit(f"数美换号失败: {json.dumps(j, ensure_ascii=False)[:300]}")
    return dev


def main() -> None:
    if not EMAIL or not PASSWORD:
        raise SystemExit("缺少 DS_EMAIL / DS_PASSWORD")

    smid = shumei_device_id()
    device_id = "B" + smid
    print("email      :", EMAIL)
    print("device_id  :", device_id[:18], "len", len(device_id))

    sess = requests.Session()
    sess.trust_env = False

    # ---- 1) 账号密码登录 ----
    body = {"email": EMAIL, "mobile": "", "area_code": "", "password": PASSWORD,
            "device_id": device_id, "os": "web", "credential_id": ""}
    r = enc_post(sess, "/api/v0/users/login", body, device_id)
    print("login      :", r.status_code, r.text[:300])
    data = r.json().get("data") or {}
    if data.get("biz_code") != 14:
        print("非 MFA 分支 biz_code =", data.get("biz_code"), data.get("biz_msg"))
        print("完整响应:", r.text[:600])
        return
    sid = data["biz_data"]["mfa_session_id"]
    print("session    :", sid, "len", len(sid))

    # ---- 2) 解数美点选 ----
    t0 = time.time()
    res = solve(batch=4, rounds=3, verbose=True)
    print(f"solve      : ok={res.get('ok')} attempts={res.get('attempts')} "
          f"elapsed={time.time() - t0:.1f}s")
    if not res.get("ok"):
        print("求解失败")
        return

    # ---- 3) 发码（该接口只接受明文 JSON，加密会 40007） ----
    payload = {
        "mfa_session_id": sid,
        "shumei_verification": {"region": "CN", "rid": res["rid"]},
        "hcaptcha_token": "",
        "shumei_device_id": smid,
        "turnstile_token": "",
    }
    rp = sess.post(BASE + TARGET, json=payload, headers=base_headers(device_id), timeout=30)
    print("mfa send   :", rp.status_code, rp.text[:300])

    state = {"device_id": device_id, "mfa_session_id": sid,
             "rid": res["rid"], "email": EMAIL, "sent_at": time.strftime("%H:%M:%S")}
    path = os.path.join(WORK, "mfa_state.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    print("state      ->", path)
    print(f"\n>>> 发码完成 {state['sent_at']}，session {sid}")
    print(">>> 请把「这一刻之后到达的那封邮件」里的 6 位码发我")


if __name__ == "__main__":
    main()
