"""打印一张图的全部检出物体（含几何特征），用于分析漏检与形状判别。

输出每个物体的：颜色/面积/质心/bbox/宽高/extent(面积÷bbox面积)/aspect/上下半宽比
"""
import json
import os
import sys

import numpy as np
import requests
from PIL import Image
from scipy import ndimage

sys.path.insert(0, r"tools")
from sm_cv2 import HUBS, hue_name  # noqa: E402
from sm_verify_probe import UA, new_uuid, register  # noqa: E402

OUT = r"work\sm\probe"
os.makedirs(OUT, exist_ok=True)


def features(img_bytes, smin=0.35, vmin=0.10, min_area=250, close=7):
    im = Image.open(__import__("io").BytesIO(img_bytes)).convert("RGB")
    hsv = np.array(im.convert("HSV"))
    h = hsv[:, :, 0].astype(np.float32) * 360.0 / 255.0
    s = hsv[:, :, 1].astype(np.float32) / 255.0
    v = hsv[:, :, 2].astype(np.float32) / 255.0
    mask = (s >= smin) & (v >= vmin)
    mask = ndimage.binary_closing(mask, structure=np.ones((close, close)))
    mask = ndimage.binary_opening(mask, structure=np.ones((3, 3)))
    lab, n = ndimage.label(mask)
    out = []
    for i in range(1, n + 1):
        ys, xs = np.where(lab == i)
        if len(xs) < min_area:
            continue
        hh = np.deg2rad(h[ys, xs])
        mh = np.rad2deg(np.arctan2(np.sin(hh).mean(), np.cos(hh).mean())) % 360
        x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
        w, hgt = x1 - x0 + 1, y1 - y0 + 1
        area = len(xs)
        # 上下半部分宽度（判断锥形）
        mid = (y0 + y1) / 2
        top = xs[ys < mid]
        bot = xs[ys >= mid]
        tw = (top.max() - top.min() + 1) if len(top) else 0
        bw = (bot.max() - bot.min() + 1) if len(bot) else 0
        out.append(
            {
                "hue": round(float(mh), 1),
                "name": hue_name(mh),
                "area": int(area),
                "cx": round(float(xs.mean()), 1),
                "cy": round(float(ys.mean()), 1),
                "w": int(w),
                "h": int(hgt),
                "extent": round(area / float(w * hgt), 3),
                "aspect": round(w / float(hgt), 3),
                "tb": round(tw / float(bw), 3) if bw else None,
            }
        )
    out.sort(key=lambda d: -d["area"])
    return out, im.size


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    for i in range(n):
        uuid = new_uuid()
        st, reg = register(uuid)
        d = reg.get("detail") or {}
        bg, order = d.get("bg"), d.get("order")
        img = requests.get("https://castatic.fengkongcloud.cn" + bg, headers={"User-Agent": UA}, timeout=20).content
        objs, size = features(img)
        print(f"\n=== [{i}] {order} size={size} n_obj={len(objs)}")
        for o in objs:
            print(f"  {o['name']:2s} hue={o['hue']:5.1f} area={o['area']:5d} c=({o['cx']:5.1f},{o['cy']:5.1f}) "
                  f"w={o['w']:3d} h={o['h']:3d} extent={o['extent']:.2f} aspect={o['aspect']:.2f} tb={o['tb']}")
        with open(os.path.join(OUT, f"{d.get('rid')}.json"), "w", encoding="utf-8") as f:
            json.dump({"order": order, "objs": objs, "size": size}, f, ensure_ascii=False, indent=1)
        open(os.path.join(OUT, f"{d.get('rid')}.jpg"), "wb").write(img)
