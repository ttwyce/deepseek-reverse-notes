"""分析点选验证码图片：颜色量化 + 连通域统计。用法: python tools/sm_img_stat.py <file>"""
import colorsys
import sys

import numpy as np
from PIL import Image


def load(path):
    im = Image.open(path).convert("RGB")
    return np.array(im)


def quantize(arr, step=24):
    q = (arr // step) * step
    flat = q.reshape(-1, 3)
    uniq, counts = np.unique(flat, axis=0, return_counts=True)
    order = np.argsort(-counts)
    out = []
    for i in order[:25]:
        c = uniq[i]
        n = int(counts[i])
        r, g, b = [int(v) for v in c]
        h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
        out.append(
            {
                "rgb": (r, g, b),
                "count": n,
                "pct": round(n / flat.shape[0] * 100, 2),
                "h": round(h * 360),
                "s": round(s * 100),
                "v": round(v * 100),
            }
        )
    return out


def main():
    p = sys.argv[1]
    a = load(p)
    h, w, _ = a.shape
    print(f"file={p} size={w}x{h}")
    for row in quantize(a):
        print(row)


if __name__ == "__main__":
    main()
