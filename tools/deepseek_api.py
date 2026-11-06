# -*- coding: utf-8 -*-
"""DeepSeek 纯协议 API 客户端（基于已授权 token）。

前置：先用 tools\\pw_get_token.py 过一次浏览器授权，产出 work\\auth_token.json。
之后所有调用都是纯 HTTP，无浏览器。

用法：
    python tools\\deepseek_api.py current
    python tools\\deepseek_api.py sessions
    python tools\\deepseek_api.py chat "你好"
    python tools\\deepseek_api.py pow /api/v0/chat/completion
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deepseek_pow import solve  # noqa: E402
from token_store import TokenStore, token_state  # noqa: E402

ROOT = Path(r"F:\dshh\deepseeka")
TOKEN_FILE = ROOT / "work" / "auth_token.json"   # 旧版明文，仅兼容
BASE = "https://chat.deepseek.com"

REFRESH_MARGIN_S = 600   # 剩余不足 10 分钟就提前静默续期

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/156.0.0.0 Safari/537.36")


class DeepSeekAPI:
    """已授权后的纯协议客户端（token 加密读取 + 自动续期）。"""

    def __init__(self, token_file: Path | None = None) -> None:
        self.store = TokenStore()
        if token_file is not None and Path(token_file).exists():
            info = json.loads(Path(token_file).read_text(encoding="utf-8"))
        else:
            info = self.store.load()          # 密文；无密文则自动迁移旧明文
        self.token: str = info["token"]
        self.device_id: str | None = info.get("device_id")
        self.uuid_device_id: str | None = (
            info.get("uuid_device_id") or str(uuid.uuid4()))
        self.session = requests.Session()
        self.session.trust_env = False
        self._refreshed = False

    # ---------- token 生命周期 ----------
    def ensure_token(self, force: bool = False) -> bool:
        """剩余有效期不足 REFRESH_MARGIN_S 时静默续期。返回 token 是否可用。"""
        st = token_state(self.token)
        left = st.get("seconds_left")
        if not force and (left is None or left > REFRESH_MARGIN_S):
            return True
        if self._refreshed and not force:
            return True
        print(f"[token] 剩余 {left}s，尝试静默续期 ...")
        try:
            from token_refresh import refresh
            r = refresh(verbose=True)
        except Exception as e:  # noqa: BLE001
            print("[token] 续期异常:", e)
            r = None
        if not r:
            print("[token] 续期失败；若接口返回 401 请重新运行 "
                  "tools\\pw_get_token.py")
            return False
        self.token = r["token"]
        self._refreshed = True
        return True

    # ---------- 基础 ----------
    def headers(self, extra: dict | None = None) -> dict:
        h = {
            "accept": "*/*",
            "accept-language": "zh-CN,zh;q=0.9",
            "content-type": "application/json",
            "origin": BASE,
            "referer": BASE + "/",
            "user-agent": UA,
            "authorization": f"Bearer {self.token}",
            "x-client-platform": "web",
            "x-client-version": "2.7.0",
            "x-client-bundle-id": "com.deepseek.chat",
            "x-client-locale": "zh_CN",
            "x-client-timezone-offset": "28800",
            "x-device-id": self.uuid_device_id,
            "x-device-model": "",
        }
        if extra:
            h.update(extra)
        return h

    def _send(self, method: str, path: str, **kw) -> requests.Response:
        url = path if path.startswith("http") else BASE + path
        self.ensure_token()
        r = self.session.request(method, url, headers=self.headers(),
                                 timeout=30, **kw)
        if r.status_code in (401, 403) and not self._refreshed:
            print(f"[token] 接口返回 {r.status_code}，续期后重试一次")
            if self.ensure_token(force=True):
                r = self.session.request(method, url, headers=self.headers(),
                                         timeout=30, **kw)
        return r

    def get(self, path: str, **kw) -> requests.Response:
        return self._send("GET", path, **kw)

    def post(self, path: str, json_body: dict | None = None,
             **kw) -> requests.Response:
        return self._send("POST", path, json=json_body, **kw)

    # ---------- PoW ----------
    def pow_header(self, target_path: str) -> str | None:
        """取 challenge → 求解 → 返回 X-DS-PoW-Response 值。"""
        r = self.post("/api/v0/chat/create_pow_challenge",
                      {"target_path": target_path})
        try:
            ch = r.json()["data"]["biz_data"]["challenge"]
        except Exception:  # noqa: BLE001
            print("[pow] challenge 获取失败:", r.status_code, r.text[:200])
            return None
        nonce = solve(ch["challenge"], ch["salt"], ch["expire_at"],
                      ch["difficulty"])
        if nonce < 0:
            print("[pow] 求解失败")
            return None
        sol = {
            "algorithm": ch.get("algorithm", "DeepSeekHashV1"),
            "challenge": ch["challenge"],
            "salt": ch["salt"],
            "signature": ch["signature"],
            "answer": nonce,
            "target_path": target_path,
        }
        import base64
        raw = json.dumps(sol, separators=(",", ":")).encode()
        print(f"[pow] nonce={nonce} for {target_path}")
        return base64.b64encode(raw).decode()

    # ---------- 业务 ----------
    def current(self) -> dict:
        r = self.get("/api/v0/users/current")
        return {"status": r.status_code, "body": _j(r)}

    def sessions(self) -> dict:
        r = self.get("/api/v0/chat_session/fetch_page?count=20")
        return {"status": r.status_code, "body": _j(r)}

    def chat(self, prompt: str, session_id: str | None = None,
             thinking: bool = False, search: bool = False) -> None:
        """流式对话（SSE）。"""
        if not session_id:
            r = self.post("/api/v0/chat_session/create", {"character_id": None})
            body = _j(r)
            sid = (body.get("data", {}).get("biz_data", {}) or {}).get("id")
            print(f"[session] create -> {r.status_code} id={sid}")
            if not sid:
                print(r.text[:400])
                return
            session_id = sid

        pow_val = self.pow_header("/api/v0/chat/completion")
        extra = {"x-ds-pow-response": pow_val} if pow_val else {}
        payload = {
            "chat_session_id": session_id,
            "parent_message_id": None,
            "prompt": prompt,
            "ref_file_ids": [],
            "thinking_enabled": thinking,
            "search_enabled": search,
        }
        url = BASE + "/api/v0/chat/completion"
        with self.session.post(url, headers=self.headers(extra), json=payload,
                               timeout=180, stream=True) as r:
            print(f"[chat] {r.status_code} {r.headers.get('content-type')}")
            if r.status_code != 200:
                print(r.text[:500])
                return
            for line in r.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith("data: "):
                    line = line[6:]
                if line == "[DONE]":
                    print("\n[DONE]")
                    break
                try:
                    obj = json.loads(line)
                except Exception:  # noqa: BLE001
                    continue
                print(json.dumps(obj, ensure_ascii=False)[:400])


def _j(r: requests.Response):
    try:
        return r.json()
    except Exception:  # noqa: BLE001
        return r.text[:500]


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    api = DeepSeekAPI()
    cmd = args[0]
    if cmd == "current":
        print(json.dumps(api.current(), ensure_ascii=False, indent=2)[:2000])
    elif cmd == "sessions":
        print(json.dumps(api.sessions(), ensure_ascii=False, indent=2)[:2000])
    elif cmd == "chat":
        api.chat(args[1] if len(args) > 1 else "你好")
    elif cmd == "pow":
        print(api.pow_header(args[1] if len(args) > 1 else "/api/v0/chat/completion"))
    elif cmd == "status":
        print(json.dumps(token_state(api.token), ensure_ascii=False, indent=2))
    elif cmd == "refresh":
        print("[ok]" if api.ensure_token(force=True) else "[fail]")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
