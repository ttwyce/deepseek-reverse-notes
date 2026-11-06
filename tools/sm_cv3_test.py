"""对比 v3(无切分) 与 v4(分水岭切分) 在已存样本上的物体检出数量。"""
import glob
import json
import os
import sys

sys.path.insert(0, r"tools")
from sm_cv3 import analyze  # noqa: E402

for jf in sorted(glob.glob(r"work\sm\probe\*.json")):
    meta = json.load(open(jf, encoding="utf-8"))
    img = open(jf[:-5] + ".jpg", "rb").read()
    order = meta["order"]
    a0 = analyze(img, order, split=False)
    a1 = analyze(img, order, split=True)
    print(f"\n{os.path.basename(jf)[:-5]} {order}")
    print(f"  no-split n={len(a0['objs'])}: {[(o['name'], o['area'], o['w'], o['h']) for o in a0['objs']]}")
    print(f"  watershed n={len(a1['objs'])}: {[(o['name'], o['area'], o['w'], o['h']) for o in a1['objs']]}")
    t = a1["target"]
    print(f"  target={a1['color']} -> {t and (int(t['cx']), int(t['cy']), t['area'])}")
