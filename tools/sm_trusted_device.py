"""DeepSeek 受信设备注册（ES256 / P-256）

流程（对照前端 work\\sm\\main.js）：
  1. POST /api/v0/users/mfa/trusted_device/register
     body {mfa_ticket, mfa_public_key: base64(SPKI DER), mfa_algorithm: "ES256"}
     headers {x-device-id: <uuid v4>, x-device-model: "", Authorization: Bearer <token>}
     -> {mfa_ticket(registerTicket), credential_id, mfa_challenge}
  2. sign = ECDSA-P256-SHA256 over "challenge\nregisterTicket\ncredentialId\nregister"
     WebCrypto 输出 64 字节 r||s，Python 侧需把 DER 拆成 r||s
  3. POST /api/v0/users/mfa/trusted_device/verify
     body {mfa_ticket: registerTicket, mfa_signature}
     -> {credential_id, expire_at}
"""
from __future__ import annotations

import base64
import json
import sys
import uuid
from pathlib import Path

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature

sys.path.insert(0, str(Path(__file__).resolve().parent))
from enc_login_test import base_headers  # noqa: E402
from token_store import TokenStore  # noqa: E402

BASE = "https://chat.deepseek.com"
WORK = Path(r"F:\dshh\deepseeka\work")
DEV_FILE = WORK / "mfa_device.json"
KEY_FILE = WORK / "mfa_key.pem"
RESULT = WORK / "trusted_device.json"


def device_uuid() -> str:
    """持久化的 UUID v4（前端 deviceSnapshot.deviceId 的格式要求）。"""
    if DEV_FILE.exists():
        try:
            d = json.loads(DEV_FILE.read_text("utf-8")).get("device_id")
            if d:
                return d
        except Exception:
            pass
    d = str(uuid.uuid4())
    DEV_FILE.write_text(json.dumps({"device_id": d}, ensure_ascii=False), "utf-8")
    return d


def load_or_create_key():
    if KEY_FILE.exists():
        return serialization.load_pem_private_key(KEY_FILE.read_bytes(), None)
    k = ec.generate_private_key(ec.SECP256R1())
    KEY_FILE.write_bytes(
        k.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return k


def spki_b64(key) -> str:
    der = key.public_key().public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return base64.b64encode(der).decode()


def sign_b64(key, challenge: str, ticket: str, credential_id: str, action: str) -> str:
    parts = [challenge, ticket, credential_id, action]
    if any((not p) or ("\r" in p) or ("\n" in p) for p in parts):
        raise ValueError("Invalid MFA signing input")
    msg = "\n".join(parts).encode("utf-8")
    der = key.sign(msg, ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    raw = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    if len(raw) != 64:
        raise ValueError("Invalid ES256 signature format")
    return base64.b64encode(raw).decode()


def get_ticket() -> str:
    store = TokenStore()
    if store.exists():
        t = (store.load() or {}).get("mfa_ticket") or ""
        if t:
            return t
    p = WORK / "auth_mfa_result.json"
    if p.exists():
        j = json.loads(p.read_text("utf-8"))
        return (j.get("data", {}).get("biz_data", {}) or {}).get("mfa_ticket", "") or ""
    return ""


def main() -> None:
    store = TokenStore()
    if not store.exists():
        print("没有 token，请先完成一次 MFA 登录")
        return
    token = store.load()["token"]
    ticket = get_ticket()
    print(f"token len: {len(token)}")
    print(f"mfa_ticket: {ticket or '(空)'}")
    if not ticket:
        print("缺少 mfa_ticket：需要重新走一次 MFA 登录")
        return

    dev = device_uuid()
    key = load_or_create_key()
    pub = spki_b64(key)
    print(f"device uuid: {dev}")
    print(f"public key (SPKI b64) len: {len(pub)}")

    sess = requests.Session()
    sess.trust_env = False
    headers = base_headers(dev)
    headers["Authorization"] = f"Bearer {token}"

    r = sess.post(
        BASE + "/api/v0/users/mfa/trusted_device/register",
        json={"mfa_ticket": ticket, "mfa_public_key": pub, "mfa_algorithm": "ES256"},
        headers=headers,
        timeout=25,
    )
    print(f"\n[register] http {r.status_code}")
    print(r.text[:900])
    try:
        j = r.json()
    except Exception:
        print("register 响应非 JSON")
        return
    if j.get("code") != 0:
        print("register 失败，mfa_ticket 可能已过期（需重新登录拿新的）")
        return

    bd = (j.get("data") or {}).get("biz_data") or {}
    rt = bd.get("mfa_ticket") or bd.get("register_ticket") or ""
    cid = bd.get("credential_id") or ""
    ch = bd.get("mfa_challenge") or ""
    print(f"registerTicket={rt!r} credential_id={cid!r} challenge={ch!r}")
    if not (rt and cid and ch):
        print("register 响应缺字段，实际 keys:", list(bd))
        return

    sig = sign_b64(key, ch, rt, cid, "register")
    print(f"signature b64 len: {len(sig)}")

    r2 = sess.post(
        BASE + "/api/v0/users/mfa/trusted_device/verify",
        json={"mfa_ticket": rt, "mfa_signature": sig},
        headers=headers,
        timeout=25,
    )
    print(f"\n[verify] http {r2.status_code}")
    print(r2.text[:900])
    try:
        j2 = r2.json()
    except Exception:
        print("verify 响应非 JSON")
        return
    if j2.get("code") != 0:
        return

    bd2 = (j2.get("data") or {}).get("biz_data") or {}
    out = {
        "credential_id": bd2.get("credential_id") or cid,
        "device_id": dev,
        "expire_at": bd2.get("expire_at"),
        "key_file": str(KEY_FILE),
    }
    RESULT.write_text(json.dumps(out, ensure_ascii=False, indent=2), "utf-8")
    print("\n受信设备注册成功 ->", RESULT)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
