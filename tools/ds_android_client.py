# -*- coding: utf-8 -*-
"""模拟 Android 真机的 DeepSeek 纯协议客户端（防封版）。

形态依据
--------
* 请求头序列取自真实 APK：work\\smali\\dex1\\ak.smali:642-965
  （x-client-platform / -version / -locale / -bundle-id / -timezone-offset /
    x-device-model）。
* UA 取舍：App 自身用 OkHttp 默认 UA（okhttp/4.12.0），但华为云 WAF 对不含
  "Mozilla" 的 UA 一律 429（实测 A/C/E 组），且 curl_cffi 无 okhttp TLS
  指纹可复刻。因此采用「Android 手机浏览器 UA」——既能过 WAF，又与
  x-client-platform: android 自洽（G/H/I 组实测 200）。

防封策略
--------
1. 设备档案持久化：device_model / android_version / x-device-id 固定不变。
2. 先访问首页拿 WAF cookie（真实浏览器行为），再发 API 请求。
3. 人类节奏：每次请求前随机间隔 1.2~3.5s，绝不并发。
4. 429 指数退避（0/3/8/20s），不硬刚。
5. PoW 必解；请求体按服务端白名单决定是否加密。
6. 单 session 复用连接与 cookie。

用法
----
    python tools\\ds_android_client.py test          # 全流程自检
    python tools\\ds_android_client.py chat "你好"
    python tools\\ds_android_client.py chat "你好" --thinking --search
    python tools\\ds_android_client.py history <session_id>
    python tools\\ds_android_client.py delete <session_id>
    python tools\\ds_android_client.py sessions
"""
from __future__ import annotations

import json
import random
import sys
import time
import uuid
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deepseek_pow import solve  # noqa: E402
from token_store import TokenStore  # noqa: E402

ROOT = Path(r"F:\dshh\deepseeka")
WORK = ROOT / "work"
PROFILE_FILE = WORK / "device_profile.json"
BASE = "https://chat.deepseek.com"

# 常见在售 Android 机型（Build.MODEL 原样值）
DEVICE_POOL = [
    ("SM-G991B", "13", "samsung"),
    ("SM-S9180", "14", "samsung"),
    ("Pixel 7", "14", "google"),
    ("2201123C", "13", "Xiaomi"),
    ("M2012K11AC", "12", "Xiaomi"),
    ("V2118A", "12", "vivo"),
    ("PGT-AN10", "13", "HUAWEI"),
    ("PGZ110", "13", "OPPO"),
]


# --------------------------------------------------------------------------- #
# 设备档案
# --------------------------------------------------------------------------- #
def android_ua(model: str, android: str, chrome: str = "156") -> str:
    return (f"Mozilla/5.0 (Linux; Android {android}; {model}) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{chrome}.0.0.0 Mobile Safari/537.36")


def load_profile() -> dict:
    """读取或首次生成设备档案（固定不变，避免设备指纹漂移）。"""
    if PROFILE_FILE.exists():
        return json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
    model, android, brand = random.choice(DEVICE_POOL)
    prof = {
        "device_model": model,
        "android_version": android,
        "brand": brand,
        "chrome_major": "156",
        "timezone_offset": 28800,          # UTC+8
        "locale": "zh_CN",
        "uuid_device_id": str(uuid.uuid4()),   # x-device-id（UUID v4）
        "created_at": int(time.time()),
    }
    PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_FILE.write_text(
        json.dumps(prof, ensure_ascii=False, indent=2), encoding="utf-8")
    return prof


# --------------------------------------------------------------------------- #
# 客户端
# --------------------------------------------------------------------------- #
class AndroidClient:
    def __init__(self, verbose: bool = True) -> None:
        self.profile = load_profile()
        info = TokenStore().load()
        self.token: str = info["token"]
        self.account_device_id: str | None = info.get("device_id")  # B<smid>
        self.session = requests.Session()
        self.session.trust_env = False
        self.ua = android_ua(self.profile["device_model"],
                             self.profile["android_version"],
                             self.profile.get("chrome_major", "156"))
        self.verbose = verbose
        self._warmed = False
        self._last_req = 0.0

    # ---------- 节奏与请求头 ----------
    def _pace(self, lo: float = 1.2, hi: float = 3.5) -> None:
        target = random.uniform(lo, hi)
        gap = time.time() - self._last_req
        if gap < target:
            time.sleep(target - gap)
        self._last_req = time.time()

    def warmup(self) -> None:
        """先像浏览器一样打开首页，拿 WAF cookie。"""
        if self._warmed:
            return
        try:
            self.session.get(BASE + "/", timeout=25, headers={
                "accept": ("text/html,application/xhtml+xml,application/xml;"
                           "q=0.9,*/*;q=0.8"),
                "accept-language": "zh-CN,zh;q=0.9",
                "user-agent": self.ua,
            })
        except Exception as e:  # noqa: BLE001
            if self.verbose:
                print("[warmup] 首页预热异常:", e)
        self._warmed = True

    def headers(self, extra: dict | None = None) -> dict:
        h = {
            "accept": "*/*",
            "accept-language": "zh-CN,zh;q=0.9",
            "user-agent": self.ua,
            "authorization": f"Bearer {self.token}",
            "x-client-platform": "android",
            "x-client-version": "2.7.1",
            "x-client-bundle-id": "com.deepseek.chat",
            "x-client-locale": self.profile["locale"],
            "x-client-timezone-offset": str(self.profile["timezone_offset"]),
            "x-device-id": self.profile["uuid_device_id"],
            "x-device-model": self.profile["device_model"],
        }
        if extra:
            h.update(extra)
        return h

    def _send(self, method: str, path: str, extra: dict | None = None, **kw):
        self.warmup()
        url = path if path.startswith("http") else BASE + path
        r = None
        for attempt, wait in enumerate([0, 3, 8, 20]):
            if wait:
                if self.verbose:
                    print(f"[waf] 429，退避 {wait}s（第 {attempt + 1} 次重试）")
                time.sleep(wait)
            self._pace()
            r = self.session.request(method, url, headers=self.headers(extra),
                                     timeout=kw.pop("timeout", 90), **kw)
            if r.status_code != 429:
                return r
        return r

    # ---------- PoW ----------
    def pow_header(self, target_path: str) -> str | None:
        r = self._send("POST", "/api/v0/chat/create_pow_challenge",
                       json={"target_path": target_path})
        try:
            ch = r.json()["data"]["biz_data"]["challenge"]
        except Exception:  # noqa: BLE001
            if self.verbose:
                print("[pow] challenge 获取失败:", r.status_code, r.text[:200])
            return None
        nonce = solve(ch["challenge"], ch["salt"], ch["expire_at"],
                      ch["difficulty"])
        if nonce < 0:
            if self.verbose:
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
        raw = json.dumps(sol, separators=(",", ":")).encode()
        if self.verbose:
            print(f"[pow] nonce={nonce} for {target_path}")
        import base64
        return base64.b64encode(raw).decode()

    # ---------- 业务 ----------
    def current(self) -> dict:
        r = self._send("GET", "/api/v0/users/current")
        return {"status": r.status_code, "body": _j(r)}

    def sessions(self, count: int = 20) -> dict:
        r = self._send("GET", "/api/v0/chat_session/fetch_page",
                       params={"count": count})
        return {"status": r.status_code, "body": _j(r)}

    def create_session(self) -> str | None:
        r = self._send("POST", "/api/v0/chat_session/create",
                       json={"character_id": None})
        body = _j(r)
        bd = (body.get("data") or {}).get("biz_data") or {}
        sid = bd.get("id") or (bd.get("chat_session") or {}).get("id")
        if self.verbose:
            print(f"[session] create {r.status_code} id={sid}")
            if not sid:
                print("  ", str(body)[:300])
        return sid

    def history(self, session_id: str) -> dict:
        r = self._send("GET", "/api/v0/chat/history_messages",
                       params={"chat_session_id": session_id})
        return {"status": r.status_code, "body": _j(r)}

    def delete_session(self, session_id: str) -> dict:
        r = self._send("POST", "/api/v0/chat_session/delete",
                       json={"chat_session_id": session_id})
        return {"status": r.status_code, "body": _j(r)}

    def stop_stream(self, session_id: str, message_id: int) -> dict:
        """停止流式生成。

        body 结构由 APK 模型 ChatStopStreamRequest（defpackage\\mr2.java）
        确认：``{chat_session_id, message_id}``；message_id 取 completion
        首个事件的 ``response_message_id``。
        """
        r = self._send("POST", "/api/v0/chat/stop_stream",
                       json={"chat_session_id": session_id,
                             "message_id": message_id})
        return {"status": r.status_code, "body": _j(r)}

    def completion(self, session_id: str, prompt: str,
                   thinking: bool = False, search: bool = False,
                   show: bool = True, on_start=None) -> dict:
        """发消息（SSE 流式）。

        ``on_start(message_id)`` 在收到首个 ``response_message_id`` 时回调，
        供调用方在流式中途调用 :meth:`stop_stream`。
        """
        pow_val = self.pow_header("/api/v0/chat/completion")
        extra = {"x-ds-pow-response": pow_val} if pow_val else {}
        payload = {
            "chat_session_id": session_id,
            "parent_message_id": None,
            "prompt": prompt,
            "ref_file_ids": [],
            "thinking_enabled": bool(thinking),
            "search_enabled": bool(search),
        }
        self.warmup()
        self._pace()
        url = BASE + "/api/v0/chat/completion"
        events: list[dict] = []
        with self.session.post(url, headers=self.headers(extra), json=payload,
                               timeout=300, stream=True) as r:
            if self.verbose:
                print(f"[chat] {r.status_code} "
                      f"{r.headers.get('content-type')}")
            if r.status_code != 200:
                return {"status": r.status_code, "events": [],
                        "text": "", "thinking": "", "raw": r.text[:500]}
            for line in r.iter_lines(decode_unicode=True):
                if not line:
                    continue
                if line.startswith("data: "):
                    line = line[6:]
                if line.strip() == "[DONE]":
                    break
                try:
                    obj = json.loads(line)
                except Exception:  # noqa: BLE001
                    continue
                events.append(obj)
                # 服务端在 FINISHED 之后仍会发标题等事件且迟迟不关连接，
                # 收到 FINISHED 即视为完成，主动断开以缩短单轮耗时。
                if obj.get("p") == "response/status" and obj.get("v") == "FINISHED":
                    break
                mid = obj.get("response_message_id")
                if on_start is not None and isinstance(mid, int):
                    cb, on_start = on_start, None
                    try:
                        cb(mid)
                    except Exception:  # noqa: BLE001
                        pass
                if show:
                    v = obj.get("v")
                    if isinstance(v, str) and (obj.get("p", "").endswith("/content")
                                               or "p" not in obj):
                        sys.stdout.write(v)
                        sys.stdout.flush()
        res = parse_events(events)
        res["status"] = 200
        res["events"] = events
        res["response_message_id"] = _first_msg_id(events)
        return res


def _first_msg_id(events: list[dict]):
    """首个事件带 response_message_id（stop_stream 需要它）。"""
    for e in events:
        v = e.get("response_message_id")
        if isinstance(v, int):
            return v
    return None


# --------------------------------------------------------------------------- #
# SSE 解析
# --------------------------------------------------------------------------- #
def _pick(d: dict, *keys):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def parse_events(events: list[dict]) -> dict:
    """解析 SSE 事件流，区分思考内容与最终回答。

    协议要点（实测 tools\\ds_android_client.py test 得到的真实序列）：
    * 带 ``p`` 的事件切换「当前路径」；只带 ``v`` 的事件延续上一个 ``p``（增量）。
    * ``p`` 以 ``/content`` 结尾时，``v`` 是增量字符串。
    * ``p == "response/fragments"`` 时，``v`` 是**完整** fragment 列表，每项含
      ``{"id", "type": "THINKING"|"RESPONSE", "content"}``。
    * 在首个 RESPONSE fragment 出现之前，``response/fragments/-1/content`` 的
      增量属于思考内容；之后属于回答。
    """
    cur: str | None = None
    frags: dict = {}
    order: list = []
    think_parts: list[str] = []
    text_parts: list[str] = []
    phase = "thinking"
    tokens = None
    status = None

    def absorb(lst: list, snapshot: bool) -> None:
        """吸收 fragment 列表。

        ``snapshot=True`` 表示来自消息快照（``{"v":{"response":{...}}}``），
        其 ``content`` 是**当前完整内容**，取更长的覆盖；否则来自
        ``p == "response/fragments"`` 的 APPEND，``content`` 是该段首片段，
        同 id 的后续 APPEND 需累加。
        """
        nonlocal phase
        for f in lst:
            if not isinstance(f, dict):
                continue
            fid = f.get("id")
            c = f.get("content") or ""
            if snapshot:
                old = frags.get(fid)
                if old is None:
                    order.append(fid)
                    frags[fid] = {"type": f.get("type"), "content": c}
                else:
                    if len(c) >= len(old["content"]):
                        old["content"] = c
                    if f.get("type"):
                        old["type"] = f.get("type")
            elif fid not in frags:
                order.append(fid)
                frags[fid] = {"type": f.get("type"), "content": c}
            else:
                # 同一 fragment 的多次 APPEND 是增量片段，必须累加
                frags[fid]["content"] += c
                if f.get("type"):
                    frags[fid]["type"] = f.get("type")
            if f.get("type") == "RESPONSE":
                phase = "text"

    for e in events:
        p, o, v = e.get("p"), e.get("o"), e.get("v")
        if p:
            cur = p
        # 消息快照事件（无 p）：{"v": {"response": {"fragments": [...]}}}
        # 首个 RESPONSE fragment 常在这里出现，必须据此切换 phase，
        # 否则后续增量会全部误归入 thinking。
        if not p and isinstance(v, dict):
            _resp = v.get("response")
            if isinstance(_resp, dict) and isinstance(_resp.get("fragments"), list):
                absorb(_resp["fragments"], snapshot=True)
                continue
        if p == "response/fragments" and isinstance(v, list):
            absorb(v, snapshot=False)
            continue
        if p == "response/status" and o == "SET":
            status = v
            continue
        if p == "response" and o == "BATCH" and isinstance(v, list):
            for it in v:
                if it.get("p") == "accumulated_token_usage":
                    tokens = it.get("v")
            continue
        if isinstance(cur, str) and cur.endswith("/content") and isinstance(v, str):
            (think_parts if phase == "thinking" else text_parts).append(v)

    think_frag = "".join(frags[i]["content"] for i in order
                         if frags[i]["type"] == "THINKING")
    text_frag = "".join(frags[i]["content"] for i in order
                        if frags[i]["type"] == "RESPONSE")
    return {
        "thinking": _merge(think_frag, think_parts),
        "text": _merge(text_frag, text_parts),
        "tokens": tokens,
        "status_msg": status,
    }


def _merge(frag: str, parts: list[str]) -> str:
    """拼接 fragment 首片段与后续增量，避免重复。

    fragment 的 content 只携带该段的**首片段**，其余内容通过
    ``response/fragments/-1/content`` 增量下发；若增量本身已包含首片段
    （以之开头），直接用增量。
    """
    s = "".join(parts)
    if not frag:
        return s
    if not s:
        return frag
    if s.startswith(frag):
        return s
    return frag + s


def _j(r) -> dict:
    try:
        return r.json()
    except Exception:  # noqa: BLE001
        return {"_text": r.text[:500]}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def cmd_test() -> None:
    c = AndroidClient()
    print("=== 设备档案 ===")
    print(json.dumps(c.profile, ensure_ascii=False, indent=2))
    print("\n=== 1. current ===")
    r = c.current()
    print(r["status"], str(r["body"])[:160])

    print("\n=== 2. create_session ===")
    sid = c.create_session()
    if not sid:
        return

    print("\n=== 3. completion（普通） ===")
    out = c.completion(sid, "用一句话介绍你自己")
    print(f"\n[文本] {out['text'][:200]!r}")
    print(f"[事件数] {len(out['events'])}")

    print("\n=== 4. history ===")
    h = c.history(sid)
    print(h["status"], str(h["body"])[:300])

    print("\n=== 5. sessions ===")
    s = c.sessions()
    print(s["status"], str(s["body"])[:200])

    print("\n=== 6. delete ===")
    d = c.delete_session(sid)
    print(d["status"], str(d["body"])[:200])


def cmd_chat(prompt: str, thinking: bool, search: bool) -> None:
    c = AndroidClient()
    sid = c.create_session()
    if not sid:
        return
    out = c.completion(sid, prompt, thinking=thinking, search=search)
    print(f"\n\n[status] {out['status']}  事件 {len(out['events'])}")
    print(f"[thinking] {out['thinking'][:200]!r}")
    print(f"[text] {out['text'][:500]!r}")


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    cmd = args[0]
    if cmd == "test":
        cmd_test()
    elif cmd == "chat":
        cmd_chat(args[1] if len(args) > 1 else "你好",
                 "--thinking" in args, "--search" in args)
    elif cmd == "history":
        c = AndroidClient()
        print(json.dumps(c.history(args[1]), ensure_ascii=False,
                         indent=2)[:3000])
    elif cmd == "delete":
        c = AndroidClient()
        print(json.dumps(c.delete_session(args[1]), ensure_ascii=False))
    elif cmd == "sessions":
        c = AndroidClient()
        print(json.dumps(c.sessions(), ensure_ascii=False, indent=2)[:3000])
    elif cmd == "current":
        c = AndroidClient()
        print(json.dumps(c.current(), ensure_ascii=False, indent=2)[:2000])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
