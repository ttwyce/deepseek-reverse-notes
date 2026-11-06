# -*- coding: utf-8 -*-
"""探测 /api/v0/users/login 的 schema：额外字段是否被接受、os 枚举范围。

422 只报 FastAPI 校验错误，不进入业务风控；用于免费摸清服务端 schema。
"""
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
import time

import requests

sys.path.insert(0, r"F:\dshh\deepseeka\tools")
from deepseek_client import BASE, DeepSeekClient  # noqa: E402

EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")


def probe(cli, body, tag, delay=4):
    r = cli.session.post(BASE + "/api/v0/users/login", headers=cli.headers(),
                         data=json.dumps(body).encode(), timeout=30)
    try:
        j = r.json()
        detail = j.get("detail")
        loc = ""
        if isinstance(detail, list):
            loc = ",".join(".".join(str(x) for x in (d.get("loc") or [])) for d in detail)
        data = j.get("data")
        biz = data.get("biz_code") if isinstance(data, dict) else None
        print(f"{tag:46s} HTTP {r.status_code} code={j.get('code')} biz={biz} loc=[{loc}] msg={j.get('msg') or (data or {}).get('biz_msg') if isinstance(data, dict) else j.get('msg')}")
    except ValueError:
        print(f"{tag:46s} HTTP {r.status_code} non-json {r.text[:100]}")
    time.sleep(delay)


def main():
    cli = DeepSeekClient(os_name="android")
    base = {"email": EMAIL, "password": PASSWORD,
            "device_id": cli.device_id, "os": "android"}

    print("== 额外字段探测（os=android 基线已通过）==")
    for field, value in [
        ("email_verification_code", "000000"),
        ("sms_verification_code", "000000"),
        ("mfa_session_id", "x"),
        ("mfa_signature", "x"),
        ("turnstile_token", ""),
        ("hcaptcha_token", ""),
        ("shumei_verification", {"rid": "", "region": "CN"}),
        ("shumei_device_id", "1.2.3.4"),
        ("captcha_token", ""),
        ("recaptcha_token", ""),
    ]:
        body = dict(base)
        body[field] = value
        probe(cli, body, f"+{field}")

    print("== os 枚举探测 ==")
    for osv in ["android", "ios", "web", "harmony", "ipad", "android_pad",
                "web_mobile", "browser", "h5", "app", "pc", "linux", "mac"]:
        body = dict(base)
        body["os"] = osv
        probe(cli, body, f"os={osv}")


if __name__ == "__main__":
    main()
