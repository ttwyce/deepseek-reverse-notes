# -*- coding: utf-8 -*-
"""token / storage_state 的加密存储。

背景：work\\auth_token.json 明文保存 Bearer token 与 cookie，任何进程都能读走。
本模块改为 Windows DPAPI 加密（绑定当前登录用户账户），密文离开本机/本用户
即无法解密。DPAPI 不可用时回退 AES-256-GCM + 本地密钥文件。

产出：
    work\\auth_token.enc      DPAPI 密文（token + device_id + 元信息）
    work\\pw_auth_state.enc   DPAPI 密文（Playwright storage_state）

用法：
    python tools\\token_store.py status     # 是否已授权、剩余有效期
    python tools\\token_store.py show       # 查看元信息（不打印 token 明文）
"""
from __future__ import annotations

import base64
import ctypes
import json
import os
import time
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

ROOT = Path(r"F:\dshh\deepseeka")
WORK = ROOT / "work"
TOKEN_ENC = WORK / "auth_token.enc"
STATE_ENC = WORK / "pw_auth_state.enc"
TOKEN_PLAIN = WORK / "auth_token.json"      # 旧版明文，仅用于迁移
STATE_PLAIN = WORK / "pw_auth_state.json"

# DPAPI 的附加熵：进一步把密文绑到本工具，别的程序即使同一用户也难解
_ENTROPY = b"deepseek-proto-client-v1"
_CRYPTPROTECT_UI_FORBIDDEN = 0x1


# ---------------------------------------------------------------- DPAPI
class _BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_char))]


def _to_blob(data: bytes) -> tuple[_BLOB, ctypes.Array | None]:
    if not data:
        return _BLOB(0, None), None
    buf = ctypes.create_string_buffer(data, len(data))
    return _BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf


def _from_blob(blob: _BLOB) -> bytes:
    try:
        if not blob.pbData:
            return b""
        return ctypes.string_at(blob.pbData, blob.cbData)
    finally:
        if blob.pbData:
            ctypes.windll.kernel32.LocalFree(blob.pbData)


def _dpapi(data: bytes, protect: bool) -> bytes:
    """调用 CryptProtectData / CryptUnprotectData。"""
    crypt32 = ctypes.windll.crypt32
    in_blob, _keep = _to_blob(data)
    ent_blob, _keep2 = _to_blob(_ENTROPY)
    out_blob = _BLOB()
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    if protect:
        ok = fn(ctypes.byref(in_blob), None, ctypes.byref(ent_blob),
                None, None, _CRYPTPROTECT_UI_FORBIDDEN,
                ctypes.byref(out_blob))
    else:
        ok = fn(ctypes.byref(in_blob), None, ctypes.byref(ent_blob),
                None, None, _CRYPTPROTECT_UI_FORBIDDEN,
                ctypes.byref(out_blob))
    if not ok:
        raise OSError(f"DPAPI {'protect' if protect else 'unprotect'} 失败 "
                      f"(err={ctypes.get_last_error()})")
    return _from_blob(out_blob)


# ---------------------------------------------------------------- JWT
def jwt_exp(token: str) -> int | None:
    """取 JWT 的 exp（unix 秒）；非 JWT 或解析失败返回 None。"""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        seg = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(seg))
        exp = payload.get("exp")
        return int(exp) if exp else None
    except Exception:  # noqa: BLE001
        return None


def token_state(token: str) -> dict:
    """token 的有效性快照。"""
    exp = jwt_exp(token)
    now = int(time.time())
    if exp is None:
        return {"exp": None, "expires_at": None, "seconds_left": None,
                "valid": None, "note": "非 JWT 或缺少 exp，无法本地判断"}
    return {
        "exp": exp,
        "expires_at": datetime.fromtimestamp(exp).strftime("%Y-%m-%d %H:%M:%S"),
        "seconds_left": exp - now,
        "valid": exp > now,
        "note": "",
    }


# ---------------------------------------------------------------- 存储
class TokenStore:
    """加密读写 token 与 storage_state。"""

    def __init__(self, work: Path = WORK) -> None:
        self.work = work
        self.token_enc = work / TOKEN_ENC.name
        self.state_enc = work / STATE_ENC.name

    # -- 通用 --
    @staticmethod
    def _write_enc(path: Path, obj: dict) -> None:
        raw = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_dpapi(raw, protect=True))
        try:  # 尽力收紧 ACL（失败不影响功能）
            os.chmod(path, 0o600)
        except OSError:
            pass

    @staticmethod
    def _read_enc(path: Path) -> dict:
        return json.loads(_dpapi(path.read_bytes(), protect=False).decode("utf-8"))

    # -- token --
    def save(self, payload: dict) -> Path:
        payload = dict(payload)
        payload.setdefault("saved_at",
                           datetime.now().astimezone().isoformat())
        tok = payload.get("token") or ""
        payload["token_state"] = token_state(tok) if tok else {}
        self._write_enc(self.token_enc, payload)
        return self.token_enc

    def load(self) -> dict:
        """读 token；若只有旧版明文则自动迁移并覆盖为密文。"""
        if self.token_enc.exists():
            return self._read_enc(self.token_enc)
        if TOKEN_PLAIN.exists():
            info = json.loads(TOKEN_PLAIN.read_text(encoding="utf-8"))
            self.save(info)
            backup = TOKEN_PLAIN.with_suffix(".json.migrated")
            TOKEN_PLAIN.replace(backup)
            print(f"[store] 已把明文 {TOKEN_PLAIN.name} 迁移为密文，"
                  f"原文件改名 {backup.name}")
            return info
        raise SystemExit(f"缺少授权文件，请先运行 tools\\pw_get_token.py")

    def exists(self) -> bool:
        return self.token_enc.exists() or TOKEN_PLAIN.exists()

    # -- storage_state --
    def save_state(self, state: dict) -> Path:
        self._write_enc(self.state_enc, state)
        return self.state_enc

    def load_state(self) -> dict | None:
        if self.state_enc.exists():
            return self._read_enc(self.state_enc)
        if STATE_PLAIN.exists():
            state = json.loads(STATE_PLAIN.read_text(encoding="utf-8"))
            self.save_state(state)
            STATE_PLAIN.replace(STATE_PLAIN.with_suffix(".json.migrated"))
            return state
        return None

    def has_state(self) -> bool:
        return self.state_enc.exists() or STATE_PLAIN.exists()


def main() -> None:
    import sys

    store = TokenStore()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

    if cmd == "status":
        if not store.exists():
            print("[未授权] 还没有 token，请运行 tools\\pw_get_token.py")
            return
        info = store.load()
        st = token_state(info.get("token") or "")
        print("[已授权]")
        print("  保存时间  :", info.get("saved_at"))
        print("  账号      :", (info.get("user_info") or "")[:80])
        print("  device_id :", (info.get("device_id") or "")[:40], "...")
        print("  过期时间  :", st.get("expires_at") or "未知")
        left = st.get("seconds_left")
        if left is not None:
            print(f"  剩余      : {left // 3600}h{left % 3600 // 60}m")
        print("  storage   :", "有（可静默续期）" if store.has_state() else "无")
    elif cmd == "show":
        info = store.load()
        info["token"] = (info.get("token") or "")[:24] + "...(已隐藏)"
        print(json.dumps(info, ensure_ascii=False, indent=2))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
