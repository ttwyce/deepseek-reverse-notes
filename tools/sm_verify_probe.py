"""数美 verify 协议探针：register 拿题 -> 构造加密 body -> JSONP GET /ca/v2/fverify。

用途：用服务端错误码反推 body 字段格式（无需渲染面板）。
"""
import base64
import json
import random
import re
import sys
import time

import requests

sys.path.insert(0, r"tools")
from sm_crypto import encrypt  # noqa: E402

ORG = "P9usCUBauxft8eAmUXaZ"
APPID = "default"
CHANNEL = "default"
LANG = "zh-cn"
RVERSION = "1.0.4"
SDKVER = "1.1.3"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
)


def new_uuid():
    # 19 位：yyyymmddHHMMSS + 5 位随机
    return time.strftime("%Y%m%d%H%M%S") + str(random.randint(10000, 99999))


def jsonp_get(url, params, timeout=15):
    cb = "sm_" + str(int(time.time() * 1000)) + str(random.randint(10, 99))
    q = {"callback": cb}
    q.update(params)
    r = requests.get(url, params=q, headers={"User-Agent": UA, "Referer": "https://chat.deepseek.com/"}, timeout=timeout)
    txt = r.text
    m = re.search(r"^\s*[\w$.]+\s*\((.*)\)\s*;?\s*$", txt, re.S)
    body = m.group(1) if m else txt
    try:
        return r.status_code, json.loads(body)
    except Exception:
        return r.status_code, {"_raw": txt[:2000]}


def register(uuid, model="spatial_select"):
    url = "https://captcha1.fengkongcloud.cn/ca/v1/register"
    params = {
        "organization": ORG,
        "lang": LANG,
        "model": model,
        "appId": APPID,
        "rversion": RVERSION,
        "sdkver": SDKVER,
        "captchaUuid": uuid,
        "channel": CHANNEL,
    }
    return jsonp_get(url, params)


def build_body(rid, uuid, select_data, mouse_data, dt, tw, th, os_name="web"):
    body = {
        "organization": ORG,
        "vf": encrypt(APPID, "3ae79dfa"),
        "ri": encrypt(CHANNEL, "fa1b1f22"),
        "cx": encrypt(LANG, "10c0600a"),
        "is": encrypt("11", "53cda785"),
        "rid": rid,
        "rversion": RVERSION,
        "sdkver": SDKVER,
        "protocol": "210",
        "ostype": "web",
        # getMouseAction()
        "pe": encrypt(select_data, "e1024477"),
        "yc": encrypt(mouse_data, "803d9d10"),
        "xt": encrypt(dt, "e6c8d743"),
        "qf": encrypt(tw, "d809f47c"),
        "qs": encrypt(th, "210a5a6d"),
        "act.os": os_name,
        "pr": encrypt("console", "f2858cfa"),
        "vn": encrypt(False, "df29aa2d"),
        "kh": encrypt(-1, "9728245c"),
        "captchaUuid": uuid,
    }
    return body


def verify(body, domain="captcha1.fengkongcloud.cn", path="/ca/v2/fverify"):
    return jsonp_get("https://" + domain + path, body)


def main():
    uuid = new_uuid()
    print("uuid =", uuid)
    st, reg = register(uuid)
    print("register", st, "code=", reg.get("code"), "risk=", reg.get("riskLevel"))
    detail = (reg.get("detail") or {})
    print("detail keys:", sorted(detail.keys()))
    print("order:", detail.get("order"), "k:", detail.get("k"), "l:", detail.get("l"))
    rid = detail.get("rid")
    bw, bh = detail.get("bg_width"), detail.get("bg_height")
    print("rid =", rid, "bg =", bw, bh)

    if not rid:
        print("NO RID, abort")
        return

    # 猜三种 selectData / mouseData 形态，各发一次
    variants = [
        ("A: [[x,y],...] + mouse 数组", [[120, 90], [300, 150], [450, 210]], [[100, 80, 0], [310, 160, 120], [460, 220, 240]]),
        ("B: [{x,y}] + 对象", [{"x": 120, "y": 90}, {"x": 300, "y": 150}, {"x": 450, "y": 210}],
         {"mx": [[100, 80]], "my": [[310, 160]]}),
        ("C: 扁平数组", [120, 90, 300, 150, 450, 210], [[100, 80, 0], [310, 160, 120], [460, 220, 240]]),
    ]
    for name, sd, md in variants:
        body = build_body(rid, uuid, sd, md, 3000, bw, bh)
        st, resp = verify(body)
        print("---", name, "->", st, json.dumps(resp, ensure_ascii=False)[:400])


if __name__ == "__main__":
    main()
