"""统计数美点选图的真实色相分布：连续 register 拿题，收集所有物体的 hue，输出聚类结果。

用法: python tools/sm_hue_stat.py --n 60 [--close 7]
"""
import argparse
import json
import sys
from collections import Counter

import numpy as np
import requests

sys.path.insert(0, r"tools")
from sm_cv2 import analyze  # noqa: E402
from sm_verify_probe import UA, new_uuid, register  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--close", type=int, default=7)
    ap.add_argument("--smin", type=float, default=0.35)
    ap.add_argument("--out", default=r"work\sm\hue_obs.jsonl")
    args = ap.parse_args()

    fh = open(args.out, "w", encoding="utf-8")
    hues, orders = [], Counter()
    for i in range(args.n):
        try:
            uuid = new_uuid()
            st, reg = register(uuid)
            d = reg.get("detail") or {}
            bg = d.get("bg")
            if not bg:
                continue
            img = requests.get("https://castatic.fengkongcloud.cn" + bg,
                               headers={"User-Agent": UA}, timeout=20).content
            a = analyze(img, d.get("order") or [], close=args.close, smin=args.smin)
            row = {"order": a["text"], "color": a["color"],
                   "objs": [(o["name"], round(o["hue"], 1), o["area"], int(o["cx"]), int(o["cy"]))
                            for o in a["objs"]]}
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            hues += [o["hue"] for o in a["objs"]]
            orders[a["color"]] += 1
            print(f"[{i+1}/{args.n}] {a['text']} -> " +
                  " ".join(f"{o['name']}{o['hue']:.0f}" for o in a["objs"]))
        except Exception as e:
            print("ERR", type(e).__name__, e)
    fh.close()

    hues = np.array(hues)
    print("\n=== 题目颜色分布 ===", dict(orders))
    hist = np.bincount((hues / 5).astype(int) % 72, minlength=72)
    print("\n=== 色相直方图 (5°一格) ===")
    for i, c in enumerate(hist):
        if c:
            print(f"{i*5:3d}-{i*5+4:3d}°  {'#'*min(c,60)} {c}")


if __name__ == "__main__":
    main()
