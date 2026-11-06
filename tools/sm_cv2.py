"""数美点选验证码图像识别 v4：整体连通域 + 亮度饱和度加权色相众数 + 最小目标。

相对 v3 的改动：
- 色相判定从「圆均值」改为「s*v 加权直方图峰值 + 邻域加权平均」，
  球体/圆锥这类明暗跨度大的物体不会再被暗面拉偏（暗面像素权重低）。
- mask 阈值放宽到 S>=0.28 / V>=0.10，闭运算 7x7，让同一物体的各个面连成一块。
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
    "蓝": ["蓝"],
    "紫": ["紫"],
    "粉": ["粉", "玫红"],
}
NB = 36  # 10 度一个 bin


def hue_name(h_deg):
    best, bd = None, 999.0
    for n, hc in HUBS.items():
        d = abs(h_deg - hc)
        d = min(d, 360 - d)
        if d < bd:
            best, bd = n, d
    return best


def dominant_hue(h_deg, weights):
    """s*v 加权直方图取峰值 bin，再在峰值 ±1 bin 内做加权平均（角度用圆周均值）。"""
    bins = np.floor((h_deg / 360.0) * NB).astype(np.int32) % NB
    hist = np.bincount(bins, weights=weights, minlength=NB)
    peak = int(hist.argmax())
    sel = (bins == peak) | (bins == (peak - 1) % NB) | (bins == (peak + 1) % NB)
    if not sel.any():
        sel = bins == peak
    hh = np.deg2rad(h_deg[sel])
    w = weights[sel]
    mean = np.rad2deg(np.arctan2((np.sin(hh) * w).sum(), (np.cos(hh) * w).sum())) % 360
    return float(mean), float(hist[peak])


def analyze(content, order, smin=0.35, vmin=0.10, min_area=250, close=7, debug=False):
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
    lab, n = ndimage.label(mask)

    objs = []
    for i in range(1, n + 1):
        ys, xs = np.where(lab == i)
        if len(xs) < min_area:
            continue
        hh, ss, vv = h[ys, xs], s[ys, xs], v[ys, xs]
        # 只用高饱和 + 较亮的部分判色（暗面/高光都不代表本色）
        sel = (ss >= 0.45) & (vv >= 0.25)
        if sel.sum() < 30:
            sel = ss >= 0.40
        if sel.sum() < 30:
            sel = np.ones(len(hh), dtype=bool)
        hue, wsum = dominant_hue(hh[sel], (ss[sel] * vv[sel]))
        objs.append(
            {
                "area": int(len(xs)),
                "hue": hue,
                "name": hue_name(hue),
                "cx": float(xs.mean()),
                "cy": float(ys.mean()),
                "bx": float((xs.min() + xs.max()) / 2),
                "by": float((ys.min() + ys.max()) / 2),
                "x0": int(xs.min()),
                "x1": int(xs.max()),
                "y0": int(ys.min()),
                "y1": int(ys.max()),
                "s": float(ss.mean()),
                "v": float(vv.mean()),
            }
        )
    objs.sort(key=lambda d: -d["area"])
    cand = [o for o in objs if o["name"] == color] if color else []
    target = min(cand, key=lambda d: d["area"]) if cand else None
    out = {"text": text, "color": color, "objs": objs, "target": target, "size": im.size}
    if debug:
        out["all"] = [(o["name"], o["area"], int(o["cx"]), int(o["cy"]), round(o["hue"])) for o in objs]
    return out
