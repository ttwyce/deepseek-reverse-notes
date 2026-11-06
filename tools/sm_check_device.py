"""探测：不同 device_id 登录时的 biz_code 差异（不发码、不消耗验证码）"""
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
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from proto_login_full import enc_post  # noqa: E402
from token_store import TokenStore  # noqa: E402

EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")
WORK = Path(r"F:\dshh\deepseeka\work")

CODE = {0: "OK", 9: "PASSWORD_WRONG", 10: "USER_BANNED", 11: "RISK_DEVICE_DETECTED",
        12: "MOBILE_RESTRICTED", 13: "SIGNATURE_REQUIRED", 14: "OTP_REQUIRED"}


def try_login(device_id: str, credential: str = "") -> None:
    sess = requests.Session()
    sess.trust_env = False
    body = {"email": EMAIL, "mobile": "", "area_code": "", "password": PASSWORD,
            "device_id": device_id, "os": "web", "credential_id": credential}
    r = enc_post(sess, "/api/v0/users/login", body, device_id)
    try:
        d = r.json().get("data") or {}
    except Exception:
        print(f"  http {r.status_code} 非 JSON: {r.text[:150]}")
        return
    code = d.get("biz_code")
    bd = d.get("biz_data") or {}
    print(f"  http {r.status_code}  biz_code={code} ({CODE.get(code, '?')})"
          f"  keys={list(bd) if isinstance(bd, dict) else bd}")
    if isinstance(bd, dict) and bd.get("mfa_session_id"):
        print(f"  mfa_session_id={bd['mfa_session_id']}  challenge={bd.get('mfa_challenge')}")


def main() -> None:
    st = TokenStore().load() or {}
    smid_dev = st.get("device_id") or ""
    print(f"token 文件里的 device_id: {smid_dev!r} (len={len(smid_dev)})")
    td = WORK / "trusted_device.json"
    uuid_dev = ""
    if td.exists():
        uuid_dev = json.loads(td.read_text("utf-8")).get("device_id", "")

    print("\n[A] 原设备 device_id（B+smid），无 credential")
    try_login(smid_dev)

    print("\n[B] 原设备 device_id（B+smid），带 credential")
    if td.exists():
        cred = json.loads(td.read_text("utf-8")).get("credential_id", "")
        try_login(smid_dev, cred)

    print(f"\n[C] 新 UUID device_id={uuid_dev}，无 credential")
    if uuid_dev:
        try_login(uuid_dev)


if __name__ == "__main__":
    main()
