"""数美点选验证码求解器 v3：整体连通域识别 + 自动重试 + 失败留档。

用法:
  python tools/sm_solve.py --n 10 [--retry 3] [--scheme pos|sel] [--debug]
"""
import argparse
import json
import os
import sys
import time

import numpy as np
import requests

sys.path.insert(0, r"tools")
from sm_crypto import encrypt  # noqa: E402
from sm_cv4 import analyze  # noqa: E402
from sm_verify_probe import UA, jsonp_get, new_uuid, register  # noqa: E402

FAILDIR = r"work\sm\fail"
os.makedirs(FAILDIR, exist_ok=True)


def build_body(rid, uuid, sd, dt, tw, th, mouse=None):
    """按数美点选类的 baseData 结构组装（参考 SDK getMouseAction）：
    mouseData = selectData = [[xr, yr, ts], ...]；xt = endTime - startTime（800~20000ms）。
    """
    md = mouse if mouse is not None else sd
    return {
        "organization": "P9usCUBauxft8eAmUXaZ",
        "vf": encrypt("default", "3ae79dfa"),
        "ri": encrypt("default", "fa1b1f22"),
        "cx": encrypt("zh-cn", "10c0600a"),
        "is": encrypt("11", "53cda785"),
        "rid": rid,
        "rversion": "1.0.4",
        "sdkver": "1.1.3",
        "protocol": "210",
        "ostype": "web",
        "pe": encrypt(sd, "e1024477"),
        "yc": encrypt(md, "803d9d10"),
        "xt": encrypt(dt, "e6c8d743"),
        "qf": encrypt(tw, "d809f47c"),
        "qs": encrypt(th, "210a5a6d"),
        "act.os": "web",
        "pr": encrypt("console", "f2858cfa"),
        "vn": encrypt(False, "df29aa2d"),
        "kh": encrypt(-1, "9728245c"),
        "captchaUuid": uuid,
    }


def verify(body, domain="captcha1.fengkongcloud.cn", path="/ca/v2/fverify"):
    return jsonp_get("https://" + domain + path, body)


def attempt(scheme="pos", disp_w=294, disp_h=147, use_bbox=True, jitter=0, save_fail=True):
    uuid = new_uuid()
    st, reg = register(uuid)
    d = reg.get("detail") or {}
    rid, bg = d.get("rid"), d.get("bg")
    if not rid or not bg:
        return {"ok": False, "stage": "register", "resp": reg}
    img = requests.get("https://castatic.fengkongcloud.cn" + bg, headers={"User-Agent": UA}, timeout=20).content
    a = analyze(img, d.get("order") or [])
    tgt = a["target"]
    if not tgt:
        if save_fail:
            open(os.path.join(FAILDIR, f"{rid}_nov.png"), "wb").write(img)
        return {"ok": False, "stage": "cv", "order": a["text"], "color": a["color"],
                "all": [(o["name"], o["area"], int(o["cx"]), int(o["cy"])) for o in a["objs"]]}
    W, H = a["size"]
    px, py = (tgt["bx"], tgt["by"]) if use_bbox else (tgt["cx"], tgt["cy"])
    if jitter:
        px += int(np.random.randint(-jitter, jitter + 1))
        py += int(np.random.randint(-jitter, jitter + 1))
    now = int(time.time() * 1000)
    if scheme == "sel":
        xr, yr = px / W - 15.0 / disp_w, py / H - 15.0 / disp_h
    else:
        xr, yr = px / W, py / H
    sd = [[round(xr, 6), round(yr, 6), now]]
    dt = int(np.random.randint(800, 20001))  # SDK: endTime - startTime = randomNum(800, 20000)
    st, resp = verify(build_body(rid, uuid, sd, dt, disp_w, disp_h))
    risk = resp.get("riskLevel")
    if risk != "PASS" and save_fail:
        open(os.path.join(FAILDIR, f"{rid}_{risk}.png"), "wb").write(img)
        json.dump({"order": a["text"], "color": a["color"], "target": tgt, "pts": sd,
                   "all": [(o["name"], o["area"], int(o["cx"]), int(o["cy"]), round(o["hue"])) for o in a["objs"]]},
                  open(os.path.join(FAILDIR, f"{rid}_{risk}.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return {
        "ok": True,
        "order": a["text"],
        "color": a["color"],
        "target": {"px": round(px, 1), "py": round(py, 1), "area": tgt["area"], "hue": round(tgt["hue"])},
        "ncand": len([o for o in a["objs"] if o["name"] == a["color"]]),
        "all": [(o["name"], o["area"], int(o["cx"]), int(o["cy"])) for o in a["objs"]],
        "pts": sd,
        "http": st,
        "code": resp.get("code"),
        "risk": risk,
        "rid": rid,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--retry", type=int, default=1)
    ap.add_argument("--scheme", default="pos", choices=["pos", "sel"])
    ap.add_argument("--disp_w", type=int, default=294)
    ap.add_argument("--disp_h", type=int, default=147)
    ap.add_argument("--centroid", action="store_true")
    ap.add_argument("--jitter", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=3.0)
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    stats = []
    for i in range(args.n):
        best = None
        for r in range(args.retry):
            try:
                res = attempt(args.scheme, args.disp_w, args.disp_h, not args.centroid, args.jitter)
            except Exception as e:
                print("ERR", type(e).__name__, e)
                res = {"ok": False, "stage": "exc"}
            best = res
            if res.get("risk") == "PASS":
                break
            time.sleep(0.5)
        stats.append(best)
        line = {k: best.get(k) for k in ("order", "color", "target", "ncand", "risk", "code", "pts")}
        if args.debug:
            line["all"] = best.get("all")
        print(json.dumps(line, ensure_ascii=False))
        time.sleep(args.sleep)
    ok = sum(1 for r in stats if r.get("risk") == "PASS")
    print(f"\n=== {ok}/{len(stats)} PASS (scheme={args.scheme}, retry={args.retry}) ===")


if __name__ == "__main__":
    main()
