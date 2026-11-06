# -*- coding: utf-8 -*-
"""验证 stop_stream：长任务流式中途停止，并检查会话历史是否落盘。

stop_stream 的 body 由 APK 模型 ChatStopStreamRequest（defpackage\\mr2.java）
确认为 ``{chat_session_id, message_id}``；message_id 来自 completion 首个事件的
``response_message_id``。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ds_android_client import BASE, AndroidClient  # noqa: E402


def main() -> None:
    c = AndroidClient(verbose=False)
    sid = c.create_session()
    if not sid:
        return

    pow_val = c.pow_header("/api/v0/chat/completion")
    extra = {"x-ds-pow-response": pow_val} if pow_val else {}
    payload = {
        "chat_session_id": sid,
        "parent_message_id": None,
        "prompt": "请写一篇 2000 字的散文，主题是秋天",
        "ref_file_ids": [],
        "thinking_enabled": True,
        "search_enabled": False,
    }

    s2 = requests.Session()
    s2.trust_env = False
    events: list[dict] = []
    stopped = False
    t0 = time.time()

    with c.session.post(BASE + "/api/v0/chat/completion",
                        headers=c.headers(extra), json=payload,
                        timeout=300, stream=True) as r:
        print("[stream]", r.status_code, r.headers.get("content-type"))
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
            mid = obj.get("response_message_id")
            if not stopped and isinstance(mid, int):
                stopped = True
                print(f"[message_id] {mid}  (首事件耗时 {time.time() - t0:.2f}s)")
                time.sleep(3.0)      # 先生成一段
                r2 = s2.post(BASE + "/api/v0/chat/stop_stream",
                             headers=c.headers(),
                             json={"chat_session_id": sid,
                                   "message_id": mid}, timeout=30)
                print("[stop_stream]", r2.status_code, r2.text[:300])
                print(f"[停止时刻] {time.time() - t0:.2f}s")

    print(f"[流已结束] {time.time() - t0:.2f}s  事件 {len(events)}")
    text = "".join(e["v"] for e in events
                   if isinstance(e.get("v"), str) and
                   str(e.get("p", "")).endswith("/content"))
    print(f"[流内文本] {len(text)} 字，尾部 {text[-60:]!r}")

    h = c.history(sid)
    body = h["body"]
    msgs = ((body.get("data") or {}).get("biz_data") or {}).get("chat_messages") or []
    print(f"[history] {h['status']} 消息数 {len(msgs)}")
    for m in msgs:
        print(f"  - id={m.get('message_id')} role={m.get('role')} "
              f"status={m.get('status')} len={len(m.get('content') or '')} "
              f"tail={(m.get('content') or '')[-40:]!r}")

    d = c.delete_session(sid)
    print("[delete]", d["status"], json.dumps(d["body"], ensure_ascii=False)[:120])


if __name__ == "__main__":
    main()
