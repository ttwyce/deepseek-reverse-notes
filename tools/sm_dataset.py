"""形状标注数据收集：register → 识别 → 提交最小同色物体 → 记录 PASS/REJECT 与全部物体特征。

PASS ⇒ 被提交物体的特征就是题目所给形状的特征（正样本）
REJECT ⇒ 该物体不是题目形状（负样本）
"""
import json
import os
import sys
import time

import numpy as np
import requests
from PIL import Image
from scipy import ndimage

sys.path.insert(0, r"tools")
from sm_crypto import encrypt  # noqa: E402
from sm_solve import build_body, verify  # noqa: E402
from sm_verify_probe import UA, new_uuid, register  # noqa: E402

OUT = r"work\sm\shape_data.jsonl"
HUBS = np.array([0.0, 38.0, 125.0, 208.0], dtype=np.float32)
HUB_NAMES = ["红", "黄", "绿", "蓝"]
SHAPES = ["球体", "圆柱体", "圆锥", "三棱锥", "三棱柱", "长方体", "六棱柱", "正方体"]


def feat_of(mask, h=None, s=None, v=None):
    ys, xs = np.where(mask)
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    bw_, bh_ = x1 - x0 + 1, y1 - y0 + 1
    area = len(xs)
    rows = []
    for y in range(y0, y1 + 1):
        r = xs[ys == y]
        rows.append(int(r.max() - r.min() + 1) if len(r) else 0)
    rows = np.array(rows, dtype=np.float32)
    maxw = float(rows.max()) if len(rows) else 1.0
    n5 = max(1, int(len(rows) * 0.05))
    mid = (y0 + y1) / 2.0
    top, bot = xs[ys < mid], xs[ys >= mid]
    tw = (top.max() - top.min() + 1) if len(top) else 0
    bw = (bot.max() - bot.min() + 1) if len(bot) else 0
    # 圆度：4πA/P²
    er = ndimage.binary_erosion(mask)
    perim = int(mask.sum() - er.sum())
    circ = round(4 * np.pi * area / (perim ** 2), 3) if perim else 0
    hue_info = {}
    if h is not None:
        hh, ss, vv = h[mask], s[mask], v[mask]
        ok = (ss >= 0.30) & (vv >= 0.10)
        if ok.sum() >= 20:
            hh, ss, vv = hh[ok], ss[ok], vv[ok]
            wgt = ss * vv
            ang = np.deg2rad(hh)
            mean_h = float(np.rad2deg(np.arctan2((np.sin(ang) * wgt).sum(), (np.cos(ang) * wgt).sum())) % 360.0)
            hue_info = {
                "hue_mean": round(mean_h, 1),
                "hue_med": round(float(np.median(hh)), 1),
                "sat": round(float(ss.mean()), 3),
                "val": round(float(vv.mean()), 3),
            }
    return {
        "area": int(area),
        "w": int(bw_),
        "h": int(bh_),
        "extent": round(area / float(bw_ * bh_), 3),
        "aspect": round(bw_ / float(bh_), 3),
        "tb": round(tw / float(bw), 3) if bw else None,
        "top1": round(float(rows[0]) / maxw, 3) if len(rows) else None,
        "top5": round(float(rows[:n5].mean()) / maxw, 3) if len(rows) else None,
        "bot5": round(float(rows[-n5:].mean()) / maxw, 3) if len(rows) else None,
        "rowstd": round(float(rows.std() / max(maxw, 1)), 3),
        "circ": circ,
        "cx": float(xs.mean()),
        "cy": float(ys.mean()),
        "bx": float((x0 + x1) / 2),
        "by": float((y0 + y1) / 2),
        "x0": x0,
        "y0": y0,
        "x1": x1,
        "y1": y1,
        **hue_info,
    }


def parse_order(order):
    t = " ".join(order) if isinstance(order, list) else str(order)
    shape = next((s for s in SHAPES if s in t), None)
    color = next((c for c in HUB_NAMES if c in t), None)
    if color is None:
        for k, v in {"红": "红", "黄": "黄", "绿": "绿", "蓝": "蓝", "橙": "黄", "青": "绿", "紫": "蓝"}.items():
            if k in t:
                color = v
                break
    return shape, color


def one():
    uuid = new_uuid()
    st, reg = register(uuid)
    d = reg.get("detail") or {}
    rid, bg, order = d.get("rid"), d.get("bg"), d.get("order")
    img = requests.get("https://castatic.fengkongcloud.cn" + bg, headers={"User-Agent": UA}, timeout=20).content
    im = Image.open(__import__("io").BytesIO(img)).convert("RGB")
    hsv = np.array(im.convert("HSV"))
    h = hsv[:, :, 0].astype(np.float32) * 360.0 / 255.0
    s = hsv[:, :, 1].astype(np.float32) / 255.0
    v = hsv[:, :, 2].astype(np.float32) / 255.0
    shape, color = parse_order(order)
    diff = np.abs(h[:, :, None] - HUBS[None, None, :])
    diff = np.minimum(diff, 360.0 - diff)
    cidx = diff.argmin(axis=2)
    base = (s >= 0.35) & (v >= 0.10)
    objs = []
    for k in range(4):
        m = base & (cidx == k)
        if m.sum() < 250:
            continue
        m = ndimage.binary_closing(m, structure=np.ones((5, 5)))
        m = ndimage.binary_opening(m, structure=np.ones((3, 3)))
        lab, n = ndimage.label(m)
        for i in range(1, n + 1):
            mm = lab == i
            if mm.sum() < 250:
                continue
            f = feat_of(mm, h, s, v)
            f["name"] = HUB_NAMES[k]
            objs.append(f)
    objs.sort(key=lambda o: -o["area"])
    cand = [o for o in objs if o["name"] == color]
    if not cand:
        return {"order": order, "shape": shape, "color": color, "skip": "no-cand",
                "objs": [{k: o[k] for k in ("name", "area", "extent", "aspect", "tb")} for o in objs]}
    tgt = min(cand, key=lambda o: o["area"])
    sd = [[round(tgt["bx"] / im.size[0], 6), round(tgt["by"] / im.size[1], 6), int(time.time() * 1000)]]
    st, resp = verify(build_body(rid, uuid, sd, 3000, 294, 147))
    return {
        "order": order,
        "shape": shape,
        "color": color,
        "risk": resp.get("riskLevel"),
        "ncand": len(cand),
        "target": tgt,
        "objs": objs,
        "rid": rid,
    }


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    with open(OUT, "a", encoding="utf-8") as f:
        for i in range(n):
            try:
                r = one()
            except Exception as e:
                print("ERR", type(e).__name__, e)
                continue
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            f.flush()
            print(f"[{i+1}/{n}] {r.get('shape')} {r.get('color')} -> {r.get('risk')} ncand={r.get('ncand')}")
            time.sleep(1.2)
    print("done ->", OUT)
