"""点选验证码图像识别：颜色分组 + 连通域找最小目标。

用法:
  python tools/sm_cv.py <img> [颜色名]        # 诊断/求解单图
  python tools/sm_cv.py --all                 # 跑 work/sm/imgs/index.json 全部
"""
import json
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

# 色相(度)区间表：name -> [(lo, hi), ...]
HUE_TABLE = {
    "红": [(0, 14), (344, 360)],
    "橙": [(14, 40)],
    "黄": [(40, 70)],
    "绿": [(70, 165)],
    "青": [(165, 196)],
    "蓝": [(196, 255)],
    "紫": [(255, 292)],
    "粉": [(292, 344)],
}
COLOR_WORDS = {
    "红": ["红"],
    "橙": ["橙"],
    "黄": ["黄"],
    "绿": ["绿"],
    "青": ["青"],
    "蓝": ["蓝"],
    "紫": ["紫"],
    "粉": ["粉", "玫红"],
}


def load_hsv(path):
    im = Image.open(path).convert("RGB")
    arr = np.array(im)
    hsv = np.array(im.convert("HSV"))
    h = hsv[:, :, 0].astype(np.float32) * 360.0 / 255.0
    s = hsv[:, :, 1].astype(np.float32) / 255.0
    v = hsv[:, :, 2].astype(np.float32) / 255.0
    return arr, h, s, v


def color_mask(h, s, v, name, smin=0.30, vmin=0.10):
    m = np.zeros(h.shape, bool)
    for lo, hi in HUE_TABLE[name]:
        m |= (h >= lo) & (h < hi)
    return m & (s >= smin) & (v >= vmin)


def blobs(mask, min_area=150, close=3):
    if close:
        mask = ndimage.binary_closing(mask, structure=np.ones((close, close)))
        mask = ndimage.binary_opening(mask, structure=np.ones((3, 3)))
    lab, n = ndimage.label(mask)
    out = []
    for i in range(1, n + 1):
        ys, xs = np.where(lab == i)
        area = len(xs)
        if area < min_area:
            continue
        out.append(
            {
                "area": int(area),
                "x0": int(xs.min()),
                "x1": int(xs.max()),
                "y0": int(ys.min()),
                "y1": int(ys.max()),
                "cx": float(xs.mean()),
                "cy": float(ys.mean()),
            }
        )
    out.sort(key=lambda d: -d["area"])
    return out


def parse_order(order):
    text = " ".join(order) if isinstance(order, list) else str(order)
    color = None
    for name, words in COLOR_WORDS.items():
        for w in words:
            if w in text:
                color = name
                break
        if color:
            break
    return color, text


def solve(path, order, smin=0.30, vmin=0.10, min_area=150):
    arr, h, s, v = load_hsv(path)
    color, text = parse_order(order)
    res = {"file": path, "order": text, "color": color, "groups": {}}
    for name in HUE_TABLE:
        m = color_mask(h, s, v, name, smin, vmin)
        bs = blobs(m, min_area)
        if bs:
            res["groups"][name] = bs
    if color and res["groups"].get(color):
        target = min(res["groups"][color], key=lambda d: d["area"])
        res["target"] = target
        res["ratio"] = [target["cx"] / arr.shape[1], target["cy"] / arr.shape[0]]
    return res


def main():
    if "--all" in sys.argv:
        idx = json.load(open(r"work\sm\imgs\index.json", encoding="utf-8"))
        for row in idx:
            r = solve(row["file"], row["order"])
            print(json.dumps({k: r.get(k) for k in ("file", "order", "color", "target", "ratio")}, ensure_ascii=False))
            for name, bs in r["groups"].items():
                print("   ", name, [(b["area"], int(b["cx"]), int(b["cy"])) for b in bs])
        return
    path = sys.argv[1]
    order = sys.argv[2:] or [""]
    r = solve(path, order)
    print(json.dumps(r, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
