"""全候选暴力尝试：rid 可多次提交，把图上所有物体按「颜色匹配优先+面积升序」逐个试。

目的：绕开漏检（目标被遮挡/面积过小）与形状误判，只要目标在检出列表里就能命中。
"""
import sys
import time

import requests

sys.path.insert(0, r"tools")
from sm_cv4 import analyze  # noqa: E402
from sm_solve import build_body, verify  # noqa: E402
from sm_verify_probe import UA, new_uuid, register  # noqa: E402


def one(idx=0, max_try=6):
    uuid = new_uuid()
    st, reg = register(uuid)
    d = reg.get("detail") or {}
    rid, bg, order = d.get("rid"), d.get("bg"), d.get("order")
    img = requests.get("https://castatic.fengkongcloud.cn" + bg, headers={"User-Agent": UA}, timeout=20).content
    a = analyze(img, order or [])
    W, H = a["size"]
    cands = sorted(a["objs"], key=lambda o: (0 if o["name"] == a["color"] else 1, o["area"]))[:max_try]
    print(f"\n=== [{idx}] {a['text']} color={a['color']} n={len(a['objs'])} rid={rid}")
    print("  全物体:", [(o["name"], o["area"], int(o["cx"]), int(o["cy"])) for o in a["objs"]])
    got = None
    for i, c in enumerate(cands):
        xr, yr = c["bx"] / W, c["by"] / H
        sd = [[round(xr, 6), round(yr, 6), int(time.time() * 1000)]]
        st, resp = verify(build_body(rid, uuid, sd, 3000, 294, 147))
        risk = resp.get("riskLevel")
        mark = "*" if c["name"] == a["color"] else " "
        print(f"  try#{i+1}{mark} {c['name']} area={c['area']:5d} ({int(c['cx'])},{int(c['cy'])}) -> {risk}")
        if risk == "PASS":
            got = i + 1
            break
        time.sleep(0.3)
    print(f"  => {'PASS at try#' + str(got) if got else 'ALL REJECT'}")
    return got, len(cands)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    res = []
    for i in range(n):
        try:
            res.append(one(i))
        except Exception as e:
            print("ERR", type(e).__name__, e)
        time.sleep(1.5)
    hit = sum(1 for g, _ in res if g)
    print(f"\n=== {hit}/{len(res)} PASS；命中位置 {[g for g, _ in res]} ===")
