"""register 拿题并下载图片到 work/sm/imgs/。用法: python tools/sm_fetch_img.py [n]"""
import json
import os
import sys
import time

import requests

sys.path.insert(0, r"tools")
from sm_verify_probe import UA, jsonp_get, new_uuid, register  # noqa: E402

OUT = r"work\sm\imgs"
os.makedirs(OUT, exist_ok=True)

n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
rows = []
for i in range(n):
    uuid = new_uuid()
    st, reg = register(uuid)
    d = reg.get("detail") or {}
    bg = d.get("bg")
    if not bg:
        print("no bg", reg.get("code"), reg.get("message"))
        continue
    url = "https://castatic.fengkongcloud.cn" + bg
    r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
    name = f"{int(time.time())}_{i}.jpg"
    p = os.path.join(OUT, name)
    open(p, "wb").write(r.content)
    row = {
        "file": p,
        "order": d.get("order"),
        "rid": d.get("rid"),
        "k": d.get("k"),
        "l": d.get("l"),
        "bg_width": d.get("bg_width"),
        "bg_height": d.get("bg_height"),
        "size": len(r.content),
        "uuid": uuid,
    }
    rows.append(row)
    print(json.dumps(row, ensure_ascii=False))

json.dump(rows, open(os.path.join(OUT, "index.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
