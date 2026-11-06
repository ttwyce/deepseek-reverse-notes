"""连续对话压测：验证防封策略在真实节奏下是否稳定。

用法：python tools\\ds_stress.py [轮数]
"""
from __future__ import annotations

import sys
import time
import traceback

sys.path.insert(0, __file__.rsplit("\\", 1)[0])

from ds_android_client import AndroidClient  # noqa: E402

PROMPTS = [
    "用一句话介绍你自己",
    "1+1 等于几？只回答数字",
    "把'你好世界'翻译成英文",
    "列出三种水果，用顿号分隔",
    "今天星期几？（按你收到请求的日期算）",
    "写一个 Python 的 hello world",
    "3 的平方是多少？只回答数字",
    "总结一下我们刚才聊了什么",
]


def main() -> int:
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 8
    c = AndroidClient(verbose=False)
    print(f"=== 压测开始，{rounds} 轮，设备 {c.profile['device_model']} ===")

    ok = 0
    codes: list[int] = []
    t_all = time.time()

    try:
        sid = c.create_session()
        print(f"[session] {sid}")
    except Exception:
        traceback.print_exc()
        return 1

    for i in range(rounds):
        prompt = PROMPTS[i % len(PROMPTS)]
        t0 = time.time()
        try:
            out = c.completion(sid, prompt, thinking=(i % 3 == 2), search=(i % 4 == 3), show=False)
            dt = time.time() - t0
            text = (out.get("text") or "").strip().replace("\n", " ")
            codes.append(int(out.get("status") or 0))
            ok += 1
            print(f"[{i+1}/{rounds}] {dt:5.2f}s status={out.get('status')} "
                  f"事件={out.get('events')} text={text[:60]!r}")
        except Exception as e:
            dt = time.time() - t0
            print(f"[{i+1}/{rounds}] {dt:5.2f}s 失败: {type(e).__name__}: {e}")
            traceback.print_exc()

    print(f"\n=== 结果 {ok}/{rounds} 成功，总耗时 {time.time()-t_all:.1f}s ===")
    print(f"状态码分布: {sorted(set(codes))}")
    print(f"429 次数: {codes.count(429)}")

    try:
        h = c.history(sid)
        bd = ((h.get("body") or {}).get("data") or {}).get("biz_data") or {}
        msgs = bd.get("chat_messages") or []
        print(f"[history] 消息数 {len(msgs)}")
        for m in msgs[:4]:
            print(f"  message_id={m.get('message_id')} role={m.get('role')} "
                  f"status={m.get('status')}")
    except Exception:
        traceback.print_exc()

    try:
        d = c.delete_session(sid)
        print(f"[delete] status={d.get('status')} "
              f"code={(d.get('body') or {}).get('code')}")
    except Exception:
        traceback.print_exc()

    return 0 if ok == rounds else 1


if __name__ == "__main__":
    raise SystemExit(main())
