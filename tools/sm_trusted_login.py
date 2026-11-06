"""DeepSeek 受信设备免 MFA 登录

对照前端 work\\sm\\main.js：
  ec() -> ed("/login", {email, mobile:"", area_code:"", password, device_id, os, credential_id}, ...)
       -> biz_code 13 (SIGNATURE_REQUIRED) + {mfa_session_id, mfa_challenge}
  sign: "challenge\\nsessionId\\ncredentialId\\nverify"
  eD() -> ed("/mfa/verify_signature", {mfa_session_id, mfa_signature}, ...)
       -> biz_code 0 (OK) + {user:{token,...}}  或 4 (OTP_REQUIRED)

两套设备标识必须分开：
  - body.device_id    = 账号原本绑定的设备（B+smid），换掉会 RISK_DEVICE_DETECTED
  - header x-device-id = 前端 deviceSnapshot（注册受信设备时用的 UUID），签名校验靠它
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



import base64
import json
import sys
from pathlib import Path

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

sys.path.insert(0, str(Path(__file__).resolve().parent))
from enc_login_test import base_headers  # noqa: E402
from proto_login_full import enc_post  # noqa: E402
from token_store import TokenStore  # noqa: E402

BASE = "https://chat.deepseek.com"
EMAIL = _cred("DS_EMAIL")
PASSWORD = _cred("DS_PASSWORD")
WORK = Path(r"F:\dshh\deepseeka\work")
TD = WORK / "trusted_device.json"
KEY = WORK / "mfa_key.pem"
OUT = WORK / "trusted_login_result.json"

SIGNATURE_REQUIRED = 13
OTP_REQUIRED = 4


def sign_b64(key, challenge: str, session_id: str, credential_id: str) -> str:
    parts = [challenge, session_id, credential_id, "verify"]
    if any((not p) or ("\r" in p) or ("\n" in p) for p in parts):
        raise ValueError("Invalid MFA signing input")
    msg = "\n".join(parts).encode("utf-8")
    der = key.sign(msg, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    return base64.b64encode(r.to_bytes(32, "big") + s.to_bytes(32, "big")).decode()


def main() -> None:
    if not TD.exists():
        print("缺少 work\\trusted_device.json，请先跑 sm_trusted_device.py")
        return
    td = json.loads(TD.read_text("utf-8"))
    cred = td["credential_id"]
    body_dev = (TokenStore().load() or {}).get("device_id") or td["device_id"]
    hdr_dev = td["device_id"]
    key = serialization.load_pem_private_key(KEY.read_bytes(), None)
    print(f"credential_id  : {cred}")
    print(f"body device_id : {body_dev}")
    print(f"header device  : {hdr_dev}")

    sess = requests.Session()
    sess.trust_env = False

    body = {
        "email": EMAIL,
        "mobile": "",
        "area_code": "",
        "password": PASSWORD,
        "device_id": body_dev,
        "os": "web",
        "credential_id": cred,
    }
    r = enc_post(sess, "/api/v0/users/login", body, hdr_dev)
    print(f"\n[login] http {r.status_code}")
    print(r.text[:400])
    j = r.json()
    data = j.get("data") or {}
    code = data.get("biz_code")
    print(f"biz_code = {code}")

    if code == 0:
        tok = ((data.get("biz_data") or {}).get("user") or {}).get("token")
        if tok:
            print("\n*** 免 MFA 直接登录成功 ***")
            OUT.write_text(json.dumps(j, ensure_ascii=False, indent=2), "utf-8")
            TokenStore().save({"token": tok, "device_id": body_dev, "smid": "",
                               "user_info": (data.get("biz_data") or {}).get("user"),
                               "mfa_ticket": "", "source": "trusted_device_login"})
            print("token len:", len(tok), "-> work\\auth_token.enc")
            return
        print("biz_code=0 但无 token")
        return

    if code != SIGNATURE_REQUIRED:
        print(f"未进入签名流程（biz_code={code}）")
        return

    bd = data.get("biz_data") or {}
    sid = bd.get("mfa_session_id") or ""
    chal = bd.get("mfa_challenge") or ""
    print(f"mfa_session_id: {sid}")
    print(f"mfa_challenge : {chal}")

    sig = sign_b64(key, chal, sid, cred)
    print(f"signature len: {len(sig)}")

    r2 = sess.post(
        BASE + "/api/v0/users/mfa/verify_signature",
        json={"mfa_session_id": sid, "mfa_signature": sig},
        headers=base_headers(hdr_dev),
        timeout=25,
    )
    print(f"\n[verify_signature] http {r2.status_code}")
    print(r2.text[:500])
    j2 = r2.json()
    d2 = j2.get("data") or {}
    c2 = d2.get("biz_code")
    print(f"biz_code = {c2}")
    if c2 == 0:
        tok = ((d2.get("biz_data") or {}).get("user") or {}).get("token")
        OUT.write_text(json.dumps(j2, ensure_ascii=False, indent=2), "utf-8")
        if tok:
            TokenStore().save({"token": tok, "device_id": body_dev, "smid": "",
                               "user_info": (d2.get("biz_data") or {}).get("user"),
                               "mfa_ticket": "", "source": "trusted_device_signature"})
            print("\n*** 签名验证通过，已免 MFA 拿到 token ***")
            print("token len:", len(tok), "-> work\\auth_token.enc")
    elif c2 == OTP_REQUIRED:
        print("服务端仍要求 OTP，说明该受信设备未被认可")
    else:
        print("verify_signature 失败")


if __name__ == "__main__":
    main()
