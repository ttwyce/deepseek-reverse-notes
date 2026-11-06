"""数美点选识别 v5：逐像素归 4 色 hub → 分色连通域 → 形状特征。

为什么按颜色分开做连通域：
  不同颜色的物体垂直粘连时（实测 红+绿 合并成 h=137 的连通域），
  只要先按颜色归类，粘连自然断开；而 4 个色 hub 间距很大
  （红0 / 黄38 / 绿125 / 蓝208，相邻间隔 38~152°），同一物体的
  亮面暗面不会被分到两个色桶，不会重演 v2 的撕裂问题。
"""
import io

import numpy as np
from PIL import Image
from scipy import ndimage

HUBS = {"红": 0, "黄": 38, "绿": 125, "蓝": 208}
HUB_ARR = np.array([0.0, 38.0, 125.0, 208.0], dtype=np.float32)
HUB_NAMES = ["红", "黄", "绿", "蓝"]
COLOR_WORDS = {"红": ["红"], "黄": ["黄", "橙"], "绿": ["绿", "青"], "蓝": ["蓝", "紫"]}


def hue_name(h):
    d = np.abs(HUB_ARR - h)
    d = np.minimum(d, 360.0 - d)
    return HUB_NAMES[int(d.argmin())]


def analyze(content, order, smin=0.35, vmin=0.10, min_area=250, close=5, debug=False):
    im = Image.open(io.BytesIO(content)).convert("RGB")
    hsv = np.array(im.convert("HSV"))
    h = hsv[:, :, 0].astype(np.float32) * 360.0 / 255.0
    s = hsv[:, :, 1].astype(np.float32) / 255.0
    v = hsv[:, :, 2].astype(np.float32) / 255.0
    text = " ".join(order) if isinstance(order, list) else str(order)
    color = next((n for n, ws in COLOR_WORDS.items() if any(w in text for w in ws)), None)

    # 逐像素归到最近的色 hub
    diff = np.abs(h[:, :, None] - HUB_ARR[None, None, :])
    diff = np.minimum(diff, 360.0 - diff)
    cidx = diff.argmin(axis=2)

    base = (s >= smin) & (v >= vmin)
    objs = []
    for k in range(4):
        m = base & (cidx == k)
        if m.sum() < min_area:
            continue
        m = ndimage.binary_closing(m, structure=np.ones((close, close)))
        m = ndimage.binary_opening(m, structure=np.ones((3, 3)))
        lab, n = ndimage.label(m)
        for i in range(1, n + 1):
            ys, xs = np.where(lab == i)
            if len(xs) < min_area:
                continue
            hh = np.deg2rad(h[ys, xs])
            mh = float(np.rad2deg(np.arctan2(np.sin(hh).mean(), np.cos(hh).mean())) % 360)
            x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
            w, hg = x1 - x0 + 1, y1 - y0 + 1
            mid = (y0 + y1) / 2.0
            top, bot = xs[ys < mid], xs[ys >= mid]
            tw = (top.max() - top.min() + 1) if len(top) else 0
            bw = (bot.max() - bot.min() + 1) if len(bot) else 0
            objs.append(
                {
                    "area": int(len(xs)),
                    "hue": round(mh, 1),
                    "name": HUB_NAMES[k],
                    "cx": float(xs.mean()),
                    "cy": float(ys.mean()),
                    "bx": float((x0 + x1) / 2),
                    "by": float((y0 + y1) / 2),
                    "w": w,
                    "h": hg,
                    "extent": round(len(xs) / float(w * hg), 3),
                    "aspect": round(w / float(hg), 3),
                    "tb": round(tw / float(bw), 3) if bw else None,
                }
            )
    objs.sort(key=lambda d: -d["area"])
    cand = [o for o in objs if o["name"] == color] if color else []
    target = min(cand, key=lambda d: d["area"]) if cand else None
    out = {"text": text, "color": color, "objs": objs, "target": target, "size": im.size}
    if debug:
        out["all"] = [(o["name"], o["area"], int(o["cx"]), int(o["cy"])) for o in objs]
    return out
