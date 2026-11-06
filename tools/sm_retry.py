"""验证「同一 captchaUuid 多次 register 换题」是否可行。

固定 uuid 连续 register N 次（每次新 rid + 新图），只提交最后一次的答案。
若 PASS ⇒ 换题策略可用：识别不确定就重新拿题，直到高置信度再提交。
"""
import json
import sys
import time

import numpy as np
import requests
from PIL import Image
from scipy import ndimage

sys.path.insert(0, r"tools")
from sm_solve import build_body, verify  # noqa: E402
from sm_verify_probe import UA, new_uuid, register  # noqa: E402

HUBS = np.array([0.0, 38.0, 125.0, 208.0], dtype=np.float32)
HUB_NAMES = ["红", "黄", "绿", "蓝"]


def analyze(img_bytes):
    im = Image.open(__import__("io").BytesIO(img_bytes)).convert("RGB")
    hsv = np.array(im.convert("HSV"))
    h = hsv[:, :, 0].astype(np.float32) * 360.0 / 255.0
    s = hsv[:, :, 1].astype(np.float32) / 255.0
    v = hsv[:, :, 2].astype(np.float32) / 255.0
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
            a = int(mm.sum())
            if a < 250:
                continue
            ys, xs = np.where(mm)
            objs.append({
                "name": HUB_NAMES[k],
                "area": a,
                "bx": float((xs.min() + xs.max()) / 2),
                "by": float((ys.min() + ys.max()) / 2),
            })
    return objs, im.size


def run(n_reg=3):
    uuid = new_uuid()
    hist = []
    for i in range(n_reg):
        st, reg = register(uuid)
        d = reg.get("detail") or {}
        rid, bg, order = d.get("rid"), d.get("bg"), d.get("order")
        hist.append({"rid": rid, "order": order, "bg": bg})
        print(f"  register#{i+1} rid={rid} order={order}")
        time.sleep(1.0)
    last = hist[-1]
    img = requests.get("https://castatic.fengkongcloud.cn" + last["bg"], headers={"User-Agent": UA}, timeout=20).content
    objs, size = analyze(img)
    t = " ".join(last["order"])
    color = next((c for c in HUB_NAMES if c in t), None)
    cand = [o for o in objs if o["name"] == color]
    print("  objs:", [(o["name"], o["area"]) for o in objs], "color:", color, "ncand:", len(cand))
    if not cand:
        print("  -> no candidate")
        return
    tgt = min(cand, key=lambda o: o["area"])
    sd = [[round(tgt["bx"] / size[0], 6), round(tgt["by"] / size[1], 6), int(time.time() * 1000)]]
    st, resp = verify(build_body(last["rid"], uuid, sd, 3000, 294, 147))
    print("  -> submit", tgt, "risk:", resp.get("riskLevel"), "code:", resp.get("code"))
    return resp.get("riskLevel")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    ok = 0
    for i in range(n):
        print(f"[{i+1}/{n}]")
        try:
            if run(3) == "PASS":
                ok += 1
        except Exception as e:
            print("  ERR", type(e).__name__, e)
        time.sleep(2.0)
    print(f"PASS {ok}/{n}")
