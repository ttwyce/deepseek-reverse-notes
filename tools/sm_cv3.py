"""数美点选识别 v4：分水岭切分粘连 + 几何特征判形状。

修复 v3 的致命问题：不同颜色的物体垂直粘连会被合并成一个连通域，
导致漏检（实测 5 个物体 vs 正常的 6 个），题目要的物体恰好被吞掉。

几何特征（实测归纳）：
  球体   aspect≈1.00  extent≈0.79
  锥形   extent≈0.55  tb≈0.6~0.72
  柱体   extent≥0.80  tb≈1.0
"""
import io

import numpy as np
from PIL import Image
from scipy import ndimage

HUBS = {"红": 0, "黄": 38, "绿": 125, "蓝": 208}
COLOR_WORDS = {
    "红": ["红"],
    "黄": ["黄", "橙"],
    "绿": ["绿", "青"],
    "蓝": ["蓝", "紫"],
}


def hue_name(h):
    best, bd = None, 999
    for n, c in HUBS.items():
        d = abs(h - c)
        d = min(d, 360 - d)
        if d < bd:
            best, bd = n, d
    return best


def split_watershed(mask, peak_size=13, peak_min=9.0, min_area=200):
    """距离变换 + 峰值种子 + 最近种子分配，切分粘连物体。"""
    dist = ndimage.distance_transform_edt(mask)
    mx = ndimage.maximum_filter(dist, size=peak_size)
    peaks = (dist >= mx - 1e-9) & (dist >= peak_min) & mask
    seeds, ns = ndimage.label(peaks)
    if ns <= 1:
        lab, n = ndimage.label(mask)
        return lab, n
    ind = ndimage.distance_transform_edt(seeds == 0, return_distances=False, return_indices=True)
    assigned = seeds[tuple(ind)].astype(np.int32)
    assigned[~mask] = 0
    # 丢弃过小的碎片（噪声峰值）
    out = np.zeros_like(assigned)
    nid = 0
    for i in range(1, ns + 1):
        m = assigned == i
        if m.sum() < min_area:
            continue
        nid += 1
        out[m] = nid
    return out, nid


def analyze(content, order, smin=0.35, vmin=0.10, min_area=250, close=7, split=True, debug=False):
    im = Image.open(io.BytesIO(content)).convert("RGB")
    hsv = np.array(im.convert("HSV"))
    h = hsv[:, :, 0].astype(np.float32) * 360.0 / 255.0
    s = hsv[:, :, 1].astype(np.float32) / 255.0
    v = hsv[:, :, 2].astype(np.float32) / 255.0
    text = " ".join(order) if isinstance(order, list) else str(order)
    color = next((n for n, ws in COLOR_WORDS.items() if any(w in text for w in ws)), None)

    mask = (s >= smin) & (v >= vmin)
    mask = ndimage.binary_closing(mask, structure=np.ones((close, close)))
    mask = ndimage.binary_opening(mask, structure=np.ones((3, 3)))

    if split:
        lab, n = split_watershed(mask, min_area=min_area)
    else:
        lab, n = ndimage.label(mask)

    objs = []
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
                "name": hue_name(mh),
                "cx": float(xs.mean()),
                "cy": float(ys.mean()),
                "bx": float((x0 + x1) / 2),
                "by": float((y0 + y1) / 2),
                "w": w,
                "h": hg,
                "extent": round(len(xs) / float(w * hg), 3),
                "aspect": round(w / float(hg), 3),
                "tb": round(tw / float(bw), 3) if bw else None,
                "x0": x0, "x1": x1, "y0": y0, "y1": y1,
            }
        )
    objs.sort(key=lambda d: -d["area"])
    cand = [o for o in objs if o["name"] == color] if color else []
    target = min(cand, key=lambda d: d["area"]) if cand else None
    out = {"text": text, "color": color, "objs": objs, "target": target, "size": im.size}
    if debug:
        out["all"] = [(o["name"], o["area"], int(o["cx"]), int(o["cy"])) for o in objs]
    return out
