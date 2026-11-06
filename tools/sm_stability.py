"""数美 verify 稳定性实验：同一 rid + 同一坐标重复提交，判断判定是否确定性。

用于区分「识别错了」与「服务端随机/风控降级」。
"""
import json
import sys
import time

import requests

sys.path.insert(0, r"tools")
from sm_cv2 import analyze  # noqa: E402
from sm_solve import build_body, verify  # noqa: E402
from sm_verify_probe import UA, new_uuid, register  # noqa: E402


def run(times=3, gap=1.0):
    uuid = new_uuid()
    st, reg = register(uuid)
    d = reg.get("detail") or {}
    rid, bg, order = d.get("rid"), d.get("bg"), d.get("order")
    img = requests.get("https://castatic.fengkongcloud.cn" + bg, headers={"User-Agent": UA}, timeout=20).content
    a = analyze(img, order or [])
    t = a["target"]
    print("order:", a["text"], "| target:", t and (round(t["bx"], 1), round(t["by"], 1), t["area"]))
    print("all:", [(o["name"], o["area"], int(o["cx"]), int(o["cy"])) for o in a["objs"]])
    if not t:
        return
    xr, yr = t["bx"] / a["size"][0], t["by"] / a["size"][1]
    print(f"\n--- 同一 rid={rid} 重复提交同一坐标 ({xr:.4f},{yr:.4f}) ---")
    for i in range(times):
        now = int(time.time() * 1000)
        sd = [[round(xr, 6), round(yr, 6), now]]
        st, resp = verify(build_body(rid, uuid, sd, 3000, 294, 147))
        print(f"  #{i+1} http={st} code={resp.get('code')} risk={resp.get('riskLevel')} "
              f"reqId={resp.get('requestId')} msg={resp.get('message')}")
        time.sleep(gap)

    print("\n--- 新 rid 重复提交同一坐标 ---")
    for i in range(times):
        u2 = new_uuid()
        st, reg2 = register(u2)
        d2 = reg2.get("detail") or {}
        r2 = d2.get("rid")
        now = int(time.time() * 1000)
        sd = [[round(xr, 6), round(yr, 6), now]]
        st, resp = verify(build_body(r2, u2, sd, 3000, 294, 147))
        print(f"  #{i+1} rid={r2} order={d2.get('order')} code={resp.get('code')} risk={resp.get('riskLevel')}")
        time.sleep(gap)


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    run(n)
