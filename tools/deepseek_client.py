# -*- coding: utf-8 -*-
"""DeepSeek 纯协议客户端（v2.7.1 / Web 端协议复刻）。

覆盖：通用请求头、GuestPow 求解、请求体 RSA+AES 混合加密、hif 令牌通道、登录与错误码解析。

用法：
    python tools/deepseek_client.py hif
    python tools/deepseek_client.py pow      # 取一次 guest challenge 并求解
    python tools/deepseek_client.py login --email a@b.com --password xxx [--os android|web]
    python tools/deepseek_client.py settings
    python tools/deepseek_client.py training                  # 读「数据用于优化体验」开关
    python tools/deepseek_client.py training --set true       # 打开（写入后回读校验）
    python tools/deepseek_client.py training --set false      # 关闭
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import uuid
from typing import Any

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from deepseek_pow import build_pow_header  # noqa: E402

BASE = "https://chat.deepseek.com"
HIF_HOSTS = {
    "dliq": "https://hif-dliq.deepseek.com/query",
    "leim": "https://hif-leim.deepseek.com/query",
}

# 网络层请求体加密公钥（o69.a，来自 p0a.smali）
RSA_PUBKEY_B64 = (
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0RLAhx1TOJhAQBHS1LHXlnkfOg86O+uhsmKW"
    "NNkmugVrRqO6cl13SnjBs2otRYZGJd50xpBG4We2i6/oCJCwxA/49YZfIwaeDmTx+WBIN7qrwhwP7vGCi"
    "6Osesmn/Ddgdye6mifYkRpRMonQjGY6VPaUMTw1jjOAIKph5YZn0bDVmGLvs5eH6CoQYHM5/Z1Nfhj36VL"
    "28eZi3elJHoz/L6Tzi2wY1rCYqYHfepq3Ysy8y5Y5BeFJXN60RYLlbs+MRC+2kyJqcfApUnn1O/W2om9dh"
    "xc6Rc5dqas1YB4X4CWCttrKk/suhpIx9zpQY9kqtotbe5zweYaKv0rCVeqx8wIDAQAB"
)

# 登录业务码
LOGIN_BIZ = {
    0: "OK",
    2: "PASSWORD_OR_USER_NAME_IS_WRONG",
    10: "USER_IS_BANNED",
    11: "RISK_DEVICE_DETECTED",
    12: "MOBILE_RESTRICTED",
    13: "SIGNATURE_REQUIRED",
    14: "OTP_REQUIRED",
}

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


# ---------------------------------------------------------------- 加密
def encrypt_request_body(plaintext: bytes) -> tuple[str, bytes]:
    """返回 (x-request-encryption-key 头值, AES-CBC 密文)。"""
    aes_key = os.urandom(16)
    iv = os.urandom(16)
    pub = serialization.load_der_public_key(base64.b64decode(RSA_PUBKEY_B64))
    wrapped = pub.encrypt(
        aes_key + iv,
        padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                     algorithm=hashes.SHA256(), label=None),
    )
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
    enc = cipher.encryptor()
    data = plaintext
    pad = 16 - len(data) % 16
    data += bytes([pad]) * pad
    return base64.b64encode(wrapped).decode(), enc.update(data) + enc.finalize()


# ---------------------------------------------------------------- 客户端
class DeepSeekClient:
    def __init__(self, device_id: str | None = None, os_name: str = "web",
                 timeout: int = 30, token: str | None = None):
        self.device_id = device_id or str(uuid.uuid4())
        self.os_name = os_name
        self.timeout = timeout
        self.token = token  # 已登录 token（Bearer），未登录接口留空即可
        self.session = requests.Session()
        self.session.trust_env = False  # 直连，避免代理 IP 触发华为云 WAF
        self.hif: dict[str, str] = {}

    # -- 头
    def headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        h = {
            "User-Agent": UA,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Content-Type": "application/json",
            "Origin": BASE,
            "Referer": BASE + "/",
            "x-client-bundle-id": "com.deepseek.chat",
            "x-client-platform": "web",
            "x-client-version": "2.7.0",
            "x-client-locale": "zh_CN",
            "x-client-timezone-offset": str(-time.timezone if time.timezone else 28800),
            "x-device-id": self.device_id,
            "x-device-model": "",
        }
        if self.hif.get("dliq"):
            h["x-hif-dliq"] = self.hif["dliq"]
        if self.hif.get("leim"):
            h["x-hif-leim"] = self.hif["leim"]
        if self.token:
            h["Authorization"] = "Bearer " + self.token
        if extra:
            h.update(extra)
        return h

    # -- hif 令牌通道（无需认证）
    def refresh_hif(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for name, url in HIF_HOSTS.items():
            try:
                r = self.session.get(url, headers=self.headers(), timeout=10)
                j = r.json()
                token = ((j.get("data") or {}).get("biz_data") or {}).get("value")
                if token:
                    self.hif[name] = token
                out[name] = {"http": r.status_code, "token_len": len(token or ""),
                             "ttl": r.headers.get("x-hif-ttl")}
            except Exception as exc:  # noqa: BLE001
                out[name] = {"error": f"{type(exc).__name__}: {exc}"}
        return out

    # -- GuestPow
    def guest_challenge(self, target_path: str) -> dict[str, Any]:
        r = self.session.post(BASE + "/api/v0/users/create_guest_challenge",
                              headers=self.headers(),
                              data=json.dumps({"target_path": target_path}).encode(),
                              timeout=self.timeout)
        payload = r.json()
        return payload["data"]["biz_data"]["guest_challenge"]

    def pow_header(self, target_path: str) -> tuple[str, int]:
        gc = self.guest_challenge(target_path)
        header, nonce = build_pow_header(gc)
        return header, nonce

    # -- 登录
    def login(self, email: str, password: str, encrypt: bool = False) -> dict[str, Any]:
        body: dict[str, Any] = {
            "email": email,
            "password": password,
            "device_id": self.device_id,
            "os": self.os_name,
            "credential_id": "",
        }
        raw = json.dumps(body).encode()
        extra: dict[str, str] = {}
        data = raw
        if encrypt:
            key_header, cipher_bytes = encrypt_request_body(raw)
            extra["x-request-encryption-key"] = key_header
            data = cipher_bytes
        r = self.session.post(BASE + "/api/v0/users/login",
                              headers=self.headers(extra), data=data,
                              timeout=self.timeout)
        return self._parse(r)

    # -- 隐私开关：「数据用于优化体验」（Web 文案 Improve the model for everyone）
    # 读：GET  /api/v0/users/settings        -> data.biz_data.training_allowed (bool)
    # 写：POST /api/v0/users/update_settings {"training_allowed": bool} -> biz_data 为 null
    #     成功响应不回显状态，必须回读 settings 校验（Web 端也是乐观更新本地缓存）
    # 头：仅 Bearer + 上述标准头；不需要 x-settings-token（那是 /client/settings 专用）、
    #     不需要 GuestPoW、body 明文 JSON 不加密（不在请求体加密白名单内）
    TOKEN_FILE = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "work", "auth_token.json")

    @classmethod
    def from_token_file(cls, path: str | None = None, **kw: Any) -> "DeepSeekClient":
        """从 work/auth_token.json（{"token","device_id",...}）构造已登录客户端。"""
        p = path or cls.TOKEN_FILE
        with open(p, encoding="utf-8") as fh:
            st = json.load(fh)
        return cls(device_id=st.get("device_id"), token=st.get("token"), **kw)

    def _require_token(self) -> None:
        if not self.token:
            raise RuntimeError("该接口需要登录态：请用 --token-file 或 token= 传入")

    def get_training_allowed(self) -> bool:
        self._require_token()
        r = self.session.get(BASE + "/api/v0/users/settings",
                             headers=self.headers(), timeout=self.timeout)
        j = r.json()
        data = j.get("data") or {}
        biz = data.get("biz_data") or {}
        if j.get("code") != 0 or "training_allowed" not in biz:
            raise RuntimeError(
                f"读取失败 HTTP {r.status_code} code={j.get('code')} "
                f"biz_code={data.get('biz_code')} biz_msg={data.get('biz_msg')!r}")
        return bool(biz["training_allowed"])

    def set_training_allowed(self, allowed: bool, verify: bool = True) -> dict[str, Any]:
        """设置训练/优化开关；verify=True 时回读确认，返回 {before, requested, after, applied}。"""
        self._require_token()
        before = self.get_training_allowed() if verify else None
        body = json.dumps({"training_allowed": bool(allowed)}).encode()
        r = self.session.post(BASE + "/api/v0/users/update_settings",
                              headers=self.headers(), data=body, timeout=self.timeout)
        out = self._parse(r)
        out["requested"] = bool(allowed)
        out["before"] = before
        if not verify:
            return out
        after = self.get_training_allowed()
        out["after"] = after
        out["applied"] = after == bool(allowed)
        return out

    # -- 其它
    def get(self, path: str) -> dict[str, Any]:
        r = self.session.get(BASE + path, headers=self.headers(), timeout=self.timeout)
        return self._parse(r)

    @staticmethod
    def _parse(r: requests.Response) -> dict[str, Any]:
        try:
            j = r.json()
        except ValueError:
            return {"http": r.status_code, "raw": r.text[:300]}
        biz = (j.get("data") or {}).get("biz_code") if isinstance(j.get("data"), dict) else None
        return {
            "http": r.status_code,
            "code": j.get("code"),
            "msg": j.get("msg"),
            "biz_code": biz,
            "biz_msg": (j.get("data") or {}).get("biz_msg") if isinstance(j.get("data"), dict) else None,
            "biz_name": LOGIN_BIZ.get(biz) if isinstance(biz, int) else None,
            "data": j.get("data"),
            "trace_id": r.headers.get("x-ds-trace-id"),
        }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("action",
                    choices=["hif", "pow", "login", "settings", "current", "training"])
    ap.add_argument("--email")
    ap.add_argument("--password")
    ap.add_argument("--os", dest="os_name", default="web")
    ap.add_argument("--encrypt", action="store_true")
    ap.add_argument("--device-id")
    ap.add_argument("--token-file",
                    help="登录态 JSON（默认 work/auth_token.json）")
    ap.add_argument("--set", dest="set_training", choices=["true", "false"],
                    help="training: 写入训练/优化开关，缺省则只读")
    args = ap.parse_args()

    cli = DeepSeekClient.from_token_file(args.token_file, os_name=args.os_name) \
        if (args.token_file or os.path.exists(DeepSeekClient.TOKEN_FILE)) \
        else DeepSeekClient(device_id=args.device_id, os_name=args.os_name)
    if args.device_id:
        cli.device_id = args.device_id
    print(f"device_id = {cli.device_id}  token={'yes' if cli.token else 'no'}")

    if args.action == "hif":
        print(json.dumps(cli.refresh_hif(), ensure_ascii=False, indent=2))
    elif args.action == "pow":
        header, nonce = cli.pow_header("/api/v0/users/create_email_verification_code")
        print(f"nonce = {nonce}\nX-DS-Guest-Pow-Response = {header[:80]}...")
    elif args.action == "login":
        if not args.email or not args.password:
            ap.error("login 需要 --email 与 --password")
        print(json.dumps(cli.login(args.email, args.password, args.encrypt),
                         ensure_ascii=False, indent=2))
    elif args.action == "settings":
        print(json.dumps(cli.get("/api/v0/client/settings"), ensure_ascii=False, indent=2))
    elif args.action == "current":
        print(json.dumps(cli.get("/api/v0/users/current"), ensure_ascii=False, indent=2))
    elif args.action == "training":
        if args.set_training is None:
            print(json.dumps({"training_allowed": cli.get_training_allowed()},
                             ensure_ascii=False, indent=2))
        else:
            want = args.set_training == "true"
            print(json.dumps(cli.set_training_allowed(want),
                             ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
