#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""DeepSeek 邮箱注册全自动流水线（无需人工抄码）。

流程: 数美换设备号 -> 数美点选求 rid -> 发验证码 -> Gmail IMAP 取码 -> register -> 校验 token

用法:
    python tools/reg_auto.py --email demo.user+5@example.com --password YOUR_PASSWORD
    python tools/reg_auto.py --email demo.user+6@example.com --password YOUR_PASSWORD --wait 180
    python tools/reg_auto.py --email a@b.com --send-only          # 只发码，不注册
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from deepseek_pow import API, HEADERS, build_pow_header  # noqa: E402
from enc_login_test import base_headers  # noqa: E402
from shumei_solver import solve  # noqa: E402
import sm_fp_client  # noqa: E402
import gmail_code  # noqa: E402

PROXY = {"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}
SM_URL = "https://fp-it-acc.portal101.cn/deviceprofile/v4"
CODE_PATH = "/api/v0/users/create_email_verification_code"
REG_PATH = "/api/v0/users/register"
RESULTS = ROOT / "work" / "reg_results.json"


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
    gc = ((r.json().get("data") or {}).get("biz_data") or {}).get("guest_challenge")
    if not gc:
        raise SystemExit("challenge 失败: " + r.text[:300])
    header, _nonce = build_pow_header(gc)
    return header


def send_code(email: str) -> str:
    """发验证码，返回 device_id。"""
    print(f"\n=== [1/4] 发码 {email} ===")
    smid = shumei_device_id()
    dev = "B" + smid
    print("device_id :", dev[:24], "len", len(dev))

    t0 = time.time()
    res = solve(batch=4, rounds=3, verbose=True)
    print(f"[solve] ok={res.get('ok')} attempts={res.get('attempts')} "
          f"elapsed={time.time()-t0:.1f}s")
    if not res.get("ok"):
        raise SystemExit("数美求解失败")

    s = session()
    payload = {
        "email": email,
        "locale": "en_US",
        "device_id": dev,
        "scenario": "register",
        "shumei_verification": {"region": "CN", "rid": res["rid"]},
        "shumei_device_id": smid,
        "hcaptcha_token": "",
        "turnstile_token": "",
    }
    r = s.post(API + CODE_PATH, json=payload, headers=base_headers(dev), timeout=40)
    print("[send] HTTP", r.status_code, r.text[:300])
    d = (r.json().get("data") or {}) if r.text.strip().startswith("{") else {}
    if d.get("biz_code") != 0:
        raise SystemExit(f"发码失败 biz_code={d.get('biz_code')} {d.get('biz_msg')}")
    print(f"[send] OK -> {email} 已发码 device_id={dev}")
    return dev


def fetch_code(email: str, wait: int, interval: int) -> str:
    print(f"\n=== [2/4] IMAP 收码（等 {wait}s）===")
    user, pw = gmail_code.load_cfg()
    conn = gmail_code.connect_plain(user, pw)
    conn.select("INBOX")
    deadline = time.time() + wait
    seen = set()
    while True:
        conn.noop()  # 关键：让服务器推送 EXISTS，否则新邮件不会出现在 search 结果里
        typ, data = conn.search(None, "ALL")
        ids = data[0].split()
        for i in reversed(ids[-10:]):
            if i in seen:
                continue
            seen.add(i)
            typ, msg_data = conn.fetch(i, "(RFC822)")
            if not msg_data or not msg_data[0]:
                continue
            import email as emailmod
            msg = emailmod.message_from_bytes(msg_data[0][1])
            to = gmail_code.decode_hdr(msg.get("To")).lower()
            subj = gmail_code.decode_hdr(msg.get("Subject"))
            if email.lower() not in to:
                continue
            code = gmail_code.extract_code(subj + "\n" + gmail_code.body_text(msg))
            if code:
                conn.logout()
                print(f"[mail] to={to[:60]} subj={subj[:60]} -> {code}")
                return code
        if time.time() > deadline:
            conn.logout()
            raise SystemExit("等码超时")
        time.sleep(interval)


def register(email: str, password: str, dev: str, code: str) -> dict:
    print(f"\n=== [3/4] 注册 code={code} ===")
    s = session()
    body = {"email": email, "email_verification_code": code, "password": password}
    outer = {"payload": body, "region": "JP", "locale": "en_US",
             "os": "android", "device_id": dev}
    h = dict(HEADERS)
    h.update(base_headers(dev))
    h["X-DS-Guest-Pow-Response"] = pow_header(s, REG_PATH)
    r = s.post(API + REG_PATH, json=outer, headers=h, timeout=40)
    print("[register] HTTP", r.status_code)
    print(r.text[:800])
    try:
        j = r.json()
    except Exception:  # noqa: BLE001
        return {"email": email, "ok": False, "raw": r.text[:400]}
    d = j.get("data") or {}
    ok = d.get("biz_code") == 0
    return {"email": email, "ok": ok, "biz_code": d.get("biz_code"),
            "biz_msg": d.get("biz_msg"), "device_id": dev, "data": d}


def check_token(token: str) -> dict:
    print("\n=== [4/4] 校验 token ===")
    s = session()
    h = dict(HEADERS)
    h["Authorization"] = "Bearer " + token
    r = s.get(API + "/api/v0/users/current", headers=h, timeout=30)
    print("[current] HTTP", r.status_code, r.text[:500])
    try:
        return r.json()
    except Exception:  # noqa: BLE001
        return {}


def append_result(rec: dict) -> None:
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    if RESULTS.exists():
        try:
            rows = json.loads(RESULTS.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            rows = []
    rows.append(rec)
    RESULTS.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print("结果已追加 ->", RESULTS)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", default=None)
    ap.add_argument("--wait", type=int, default=120, help="等邮件秒数")
    ap.add_argument("--interval", type=int, default=4)
    ap.add_argument("--send-only", action="store_true")
    a = ap.parse_args()

    pw = a.password
    if not pw:
        import local_config  # type: ignore
        pw = local_config.CFG.get("DS_PASSWORD")
    if not pw:
        sys.exit("缺少密码：--password 或 tools/local_config.py 的 DS_PASSWORD")

    dev = send_code(a.email)
    if a.send_only:
        return
    code = fetch_code(a.email, a.wait, a.interval)
    rec = register(a.email, pw, dev, code)
    if rec.get("ok"):
        bd = (rec.get("data") or {}).get("biz_data") or {}
        token = (bd.get("user") or {}).get("token") or bd.get("token")
        if token:
            cur = check_token(token)
            rec["token"] = token
            rec["current"] = cur
            rec["user_id"] = ((cur.get("data") or {}).get("biz_data") or {}).get("user", {}).get("id") \
                or (bd.get("user") or {}).get("id")
    append_result(rec)
    print("\n=== 完成 ===", "成功" if rec.get("ok") else "失败")


if __name__ == "__main__":
    main()
