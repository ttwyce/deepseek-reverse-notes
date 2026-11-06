# -*- coding: utf-8 -*-
"""DeepSeek 邮箱注册全流程（日本 IP + 数美真 rid 过 captcha）。

用法：
    python tools\\reg_flow.py send             # 换设备号 -> 解数美 -> 发验证码，保存 state
    python tools\\reg_flow.py verify 123456    # 用 state 里的 device_id 提交注册
    python tools\\reg_flow.py show             # 查看 state
"""
from __future__ import annotations

import json
import os
import sys
import time

import requests

sys.path.insert(0, r"F:\dshh\deepseeka\tools")
from deepseek_pow import API, HEADERS, build_pow_header  # noqa: E402
from enc_login_test import base_headers  # noqa: E402
from shumei_solver import solve  # noqa: E402
import sm_fp_client  # noqa: E402

PROXY = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
SM_URL = "https://fp-it-acc.portal101.cn/deviceprofile/v4"
CODE_PATH = "/api/v0/users/create_email_verification_code"
REG_PATH = "/api/v0/users/register"
# 凭据不落盘：邮箱可用 --email 或 DS_REG_EMAIL，密码必须走环境变量 DS_REG_PASSWORD
EMAIL = os.environ.get("DS_REG_EMAIL", "demo.user+4@example.com")
PASSWORD = os.environ.get("DS_REG_PASSWORD", "")
STATE = r"F:\dshh\deepseeka\work\reg_state.json"


def session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False
    s.proxies = PROXY
    return s


def shumei_device_id() -> str:
    _uid, _pri, body = sm_fp_client.build_request(
        sm_fp_client.build_fields(sm_fp_client.load_template()))
    r = requests.post(SM_URL, json=body, headers=sm_fp_client.HEADERS,
                      proxies=PROXY, timeout=20)
    j = r.json()
    dev = ((j.get("detail") or {}).get("deviceId") or "")
    print(f"[shumei] code={j.get('code')} deviceId_len={len(dev)}")
    if j.get("code") != 1100 or len(dev) != 88:
        raise SystemExit("数美换号失败: " + json.dumps(j, ensure_ascii=False)[:300])
    return dev


def pow_header(s: requests.Session, path: str) -> str:
    r = s.post(API + "/api/v0/users/create_guest_challenge",
               json={"target_path": path}, headers=HEADERS, timeout=30)
    gc = (r.json().get("data") or {}).get("biz_data", {}).get("guest_challenge")
    if not gc:
        raise SystemExit("challenge 失败: " + r.text[:300])
    header, _nonce = build_pow_header(gc)
    return header


def do_send() -> None:
    smid = shumei_device_id()
    dev = "B" + smid
    print("device_id :", dev[:20], "len", len(dev))

    t0 = time.time()
    res = solve(batch=4, rounds=3, verbose=True)
    print(f"[solve] ok={res.get('ok')} attempts={res.get('attempts')} "
          f"elapsed={time.time()-t0:.1f}s")
    if not res.get("ok"):
        raise SystemExit("数美求解失败")

    s = session()
    payload = {
        "email": EMAIL,
        "locale": "en_US",
        "device_id": dev,
        "scenario": "register",
        "shumei_verification": {"region": "CN", "rid": res["rid"]},
        "shumei_device_id": smid,
        "hcaptcha_token": "",
        "turnstile_token": "",
    }
    r = s.post(API + CODE_PATH, json=payload, headers=base_headers(dev), timeout=40)
    print("[send] HTTP", r.status_code, r.text[:400])
    d = (r.json().get("data") or {}) if r.text.strip().startswith("{") else {}
    if d.get("biz_code") != 0:
        raise SystemExit("发码失败: " + r.text[:300])

    st = {"device_id": dev, "smid": smid, "rid": res["rid"], "email": EMAIL,
          "sent_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=2)
    print("state ->", STATE)
    print(f"\n>>> 验证码已发送到 {EMAIL}，把 6 位码给我即可（命令：verify <code>）")


def do_verify(code: str) -> None:
    with open(STATE, encoding="utf-8") as f:
        st = json.load(f)
    dev = st["device_id"]
    print("device_id :", dev[:20], "len", len(dev), "| sent", st["sent_at"])

    s = session()
    pw = PASSWORD or os.environ.get("DS_REG_PASSWORD", "")
    if not pw:
        sys.exit("缺少密码：请先设置环境变量 DS_REG_PASSWORD")
    body = {"email": st["email"], "email_verification_code": code,
            "password": pw}
    outer = {"payload": body, "region": "JP", "locale": "en_US",
             "os": "android", "device_id": dev}
    h = dict(HEADERS)
    h.update(base_headers(dev))
    h["X-DS-Guest-Pow-Response"] = pow_header(s, REG_PATH)
    r = s.post(API + REG_PATH, json=outer, headers=h, timeout=40)
    print("[register] HTTP", r.status_code)
    print(r.text[:1200])

    try:
        j = r.json()
    except Exception:
        return
    d = j.get("data") or {}
    print(f"\nbiz_code={d.get('biz_code')} biz_msg={d.get('biz_msg')}")
    if d.get("biz_code") == 0:
        out = r"F:\dshh\deepseeka\work\reg_result.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(j, f, ensure_ascii=False, indent=2)
        print("注册成功，结果 ->", out)


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "show"
    if cmd == "send":
        do_send()
    elif cmd == "verify":
        if len(sys.argv) < 3:
            raise SystemExit("用法: verify <6位验证码>")
        do_verify(sys.argv[2].strip())
    else:
        if os.path.exists(STATE):
            print(open(STATE, encoding="utf-8").read())
        else:
            print("尚无 state，先运行 send")


if __name__ == "__main__":
    main()
