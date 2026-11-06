"""数美 spatial_select（点选）验证码求解器 —— 纯 Python 协议复刻。

不依赖浏览器、不渲染面板，全流程走 HTTP：
    register 拿题 -> 下载图片 -> 分色连通域识别目标物体 -> DES 加密答案 -> JSONP verify

核心结论（逆向自 captcha-sdk.min.js v1.0.4-210）：
- 传输：GET + JSONP，全部字段在 query，回调名 sm_<rand>，成功判据 code==1100
- 加密：DES-ECB(key=salt 的 8 字节 ASCII, 明文 UTF8 补 \\0 对齐) + base64
- 一次性：同一 rid 只有第一次 verify 有效，失败后该 rid 作废
- 因此策略为「多 uuid 并发拿题 + 串行提交，第一个 PASS 即返回」

用法：
    from shumei_solver import solve
    r = solve()                      # {'ok': True, 'rid': ..., 'attempts': 3, 'elapsed': 4.2}
    python tools/shumei_solver.py    # 命令行自测
"""
import concurrent.futures as cf
import sys
import time

import numpy as np
import requests

sys.path.insert(0, r"tools")
from sm_cv4 import analyze  # noqa: E402
from sm_solve import build_body, verify  # noqa: E402
from sm_verify_probe import UA, new_uuid, register  # noqa: E402

IMG_BASE = "https://castatic.fengkongcloud.cn"
DISP_W, DISP_H = 294, 147  # embed 面板里图片的显示尺寸（600x300 图等比缩放）


def fetch(uuid):
    """register 拿题并下载图片。"""
    st, reg = register(uuid)
    d = reg.get("detail") or {}
    rid, bg = d.get("rid"), d.get("bg")
    if not rid or not bg:
        return None
    try:
        img = requests.get(IMG_BASE + bg, headers={"User-Agent": UA}, timeout=20).content
    except Exception:
        return None
    return {"uuid": uuid, "rid": rid, "img": img, "order": d.get("order") or []}


def plan(t):
    """识别目标物体，算出归一化点击坐标。"""
    try:
        a = analyze(t["img"], t["order"])
    except Exception:
        return None
    tgt = a.get("target")
    if not tgt:
        return None
    W, H = a["size"]
    return dict(t, px=float(tgt["bx"]), py=float(tgt["by"]), W=W, H=H,
                order_text=a["text"], color=a["color"], area=tgt["area"])


def submit(p):
    """构造加密 body 并提交 verify。"""
    now = int(time.time() * 1000)
    sd = [[round(p["px"] / p["W"], 6), round(p["py"] / p["H"], 6), now]]
    dt = int(np.random.randint(800, 20001))
    st, resp = verify(build_body(p["rid"], p["uuid"], sd, dt, DISP_W, DISP_H))
    return resp.get("riskLevel"), resp


def solve(batch=4, rounds=3, verbose=False, sleep=0.3):
    """求解一次数美点选验证码。

    batch  : 每轮并发拿题数（每个独立 captchaUuid）
    rounds : 最多几轮；总尝试上限 = batch * rounds
    返回 {'ok': bool, 'rid': str, 'uuid': str, 'attempts': int, 'elapsed': float, 'order': str}
    """
    t0 = time.time()
    attempts = 0
    last = None
    for rnd in range(rounds):
        uuids = [new_uuid() for _ in range(batch)]
        with cf.ThreadPoolExecutor(max_workers=batch) as ex:
            got = [x for x in ex.map(fetch, uuids) if x]
        if not got:
            continue
        with cf.ThreadPoolExecutor(max_workers=len(got)) as ex:
            plans = [x for x in ex.map(plan, got) if x]
        for p in plans:
            attempts += 1
            try:
                risk, resp = submit(p)
            except Exception as e:
                risk, resp = "ERR:" + type(e).__name__, {}
            last = {"order": p["order_text"], "color": p["color"], "area": p["area"],
                    "px": p["px"], "py": p["py"], "risk": risk, "code": resp.get("code")}
            if verbose:
                print(f"  [{attempts}] {p['order_text']} -> {risk}", flush=True)
            if risk == "PASS":
                return {"ok": True, "rid": p["rid"], "uuid": p["uuid"], "attempts": attempts,
                        "elapsed": round(time.time() - t0, 2), "order": p["order_text"],
                        "last": last}
            time.sleep(sleep)
    return {"ok": False, "attempts": attempts, "elapsed": round(time.time() - t0, 2), "last": last}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3, help="自测轮数")
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    ok, total, ts = 0, 0, []
    for i in range(args.n):
        r = solve(batch=args.batch, rounds=args.rounds, verbose=args.verbose)
        total += 1
        ts.append(r["elapsed"])
        if r["ok"]:
            ok += 1
        print(f"[{i+1}/{args.n}] ok={r['ok']} attempts={r['attempts']} "
              f"elapsed={r['elapsed']}s order={r.get('order')}", flush=True)
        time.sleep(1.0)
    print(f"\n=== {ok}/{total} PASS, 平均耗时 {sum(ts)/len(ts):.2f}s "
          f"(batch={args.batch}, rounds={args.rounds}) ===")


if __name__ == "__main__":
    main()
