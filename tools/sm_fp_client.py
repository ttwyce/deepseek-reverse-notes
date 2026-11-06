"""数美 deviceprofile/v4 纯协议客户端：复刻 fp.min.js 的全部封装，拿真 deviceId。

链路（静态逆向 + 抓包双向确认）：
  指纹对象 -> JSON -> pako gzip -> base64        （compress:2）
           -> AES-128-CBC(key=md5(uid)[:16], iv='0102030405060708', ZeroPadding) -> hex   （encode:5）
  ep       -> RSA-PKCS1v15(publicKey, uid) -> base64
  单字段   -> base64(DES-ECB(key=8字符混淆名, ZeroPadding(值)))

用法：
  python tools/sm_fp_client.py            # 生成并请求，打印 deviceId
  python tools/sm_fp_client.py --selftest # 只做本地自检（canon/uq/smid/DES）
"""
import base64
import gzip
import hashlib
import json
import os
import random
import sys
import time
import uuid

import requests
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, modes
from cryptography.hazmat.primitives.serialization import load_der_public_key

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sm_crypto import encrypt as des_encrypt  # noqa: E402  DES-ECB + ZeroPadding + base64

try:
    from cryptography.hazmat.decrepit.ciphers.algorithms import TripleDES, AES
except Exception:  # pragma: no cover
    from cryptography.hazmat.primitives.ciphers.algorithms import TripleDES, AES

API = "https://fp-it-acc.portal101.cn/deviceprofile/v4"
ORG = "P9usCUBauxft8eAmUXaZ"
APPID = "default"
PUBKEY = ("MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDetfEgYD4aE1ZjmWJ6/jnPurhzI+yeRoJHWrnNtQMte3st"
          "Q4VjG3yu21FuN75E6cDpA9KtDXwcB2M/FiGUAe3G0rNotbWI8+SjZfUbW/OILFTzY0uaeEkmVGW5WyJ6we"
          "Qbbr1xTCPa2OO3YIMeZljWUYHG5h21WAm/PATg8im8cQIDAQAB")
IV = b"0102030405060708"
HERE = os.path.dirname(os.path.abspath(__file__))
# 仓库自带指纹模板（真实浏览器一次性快照，81 字段，含原始 uq）
TEMPLATE = os.path.join(HERE, "sm_fp_template.json")
# 回退：抓包脚本 sm_fp_plain.py 的原始产物（work/ 不入库）
TEMPLATE_LEGACY = os.path.join("work", "sm", "fp", "plain.json")


def load_template() -> dict:
    """读取指纹模板：优先仓库自带副本，其次回退到抓包原始产物。"""
    if os.path.exists(TEMPLATE):
        with open(TEMPLATE, encoding="utf-8") as f:
            return json.load(f)
    if os.path.exists(TEMPLATE_LEGACY):
        with open(TEMPLATE_LEGACY, encoding="utf-8") as f:
            return json.loads(json.load(f)[0]["str"])
    raise SystemExit(f"找不到指纹模板：{TEMPLATE}（或先跑 sm_fp_plain.py 生成 {TEMPLATE_LEGACY}）")

# 字段混淆名（fp.min.js 里 des_sm/字段封装用的 8 字符 key，已逐个穷举解密验证）
K = {
    "bl": "6nprv5u4", "xi": "fosnye0h", "tf": "uuikiial", "nv": "ktq3h98y",
    "cz": "bp4e16vc", "mx": "holed4zr", "pf": "7i0ulooq", "nm": "t05aq73a",
    "up": "zk8fnud4", "lh": "ws3dvpoz", "ge": "bhibsj62", "rn": "2dia2cb3",
    "nw": "2mcfum7k", "rg": "aj5ukhl0", "mh": "02n6f6c9", "dy": "3n5fm4fb",
    "kt": "v3ybya7s", "xy": "pi016hk4", "iy": "d5htj6gi", "pz": "dtx3qb8x",
    "uq": "ozmby6ug",
}


# ---------------------------------------------------------------- 基础算法
def md5_hex(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def canon(obj: dict) -> str:
    """复刻 _0x112781：只对顶层对象按键名排序拼接，字段值一律 String(v)（对象变 [object Object]）。"""
    out = []
    for k in sorted(obj.keys()):
        v = obj[k]
        if isinstance(v, bool):
            out.append("true" if v else "false")
        elif isinstance(v, (int, float)):
            n = 10000 * v
            out.append(str(int(n)) if float(n).is_integer() else repr(n))
        elif v is None:
            out.append("null")
        elif isinstance(v, str):
            out.append(v)
        elif isinstance(v, list):
            out.append(",".join("true" if e is True else "false" if e is False else str(e) for e in v))
        else:
            out.append("[object Object]")
    return "".join(out)


def aes_encrypt_hex(plain: str, key: str) -> str:
    """AES-CBC + ZeroPadding，key 为 16 字节 ASCII，IV 固定，输出小写 hex。"""
    raw = plain.encode("utf-8")
    pad = (-len(raw)) % 16
    raw += b"\x00" * pad
    c = Cipher(AES(key.encode("utf-8")), modes.CBC(IV))
    e = c.encryptor()
    return (e.update(raw) + e.finalize()).hex()


def aes_decrypt_hex(cipher_hex: str, key: str) -> bytes:
    c = Cipher(AES(key.encode("utf-8")), modes.CBC(IV))
    d = c.decryptor()
    return (d.update(bytes.fromhex(cipher_hex)) + d.finalize()).rstrip(b"\x00")


def gzip_b64(obj: dict) -> str:
    """复刻 gzip()：JSON.stringify -> pako gzip -> btoa（等价 base64(gzip bytes)）。"""
    raw = json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.b64encode(gzip.compress(raw, compresslevel=6, mtime=0)).decode()


def rsa_encrypt_b64(msg: str, pub_b64: str = PUBKEY) -> str:
    pub = load_der_public_key(base64.b64decode(pub_b64))
    return base64.b64encode(pub.encrypt(msg.encode("utf-8"), asym_padding.PKCS1v15())).decode()


def get_localsmid() -> str:
    """复刻 getLocalsmid()：YYYYMMDDHHMMSS + md5(rand) + '00' + md5('smsk_web_'+base)[:14] + '0'。"""
    t = time.localtime()
    ts = (f"{t.tm_year:04d}{t.tm_mon:02d}{t.tm_mday:02d}"
          f"{t.tm_hour:02d}{t.tm_min:02d}{t.tm_sec:02d}")
    r = str(uuid.uuid4())
    base = ts + md5_hex(r) + "00"
    return base + md5_hex("smsk_web_" + base)[:14] + "0"


def js_date_string() -> str:
    """复刻 JS 的 new Date().toString()（含中文时区名）。"""
    t = time.localtime()
    wd = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][t.tm_wday]
    mo = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][t.tm_mon - 1]
    off = -time.timezone if t.tm_isdst == 0 else -time.altzone
    sign = "+" if off >= 0 else "-"
    off = abs(off) // 60
    return (f"{wd} {mo} {t.tm_mday:02d} {t.tm_year} {t.tm_hour:02d}:{t.tm_min:02d}:{t.tm_sec:02d} "
            f"GMT{sign}{off // 60:02d}{off % 60:02d} (中国标准时间)")


# ---------------------------------------------------------------- 组包
def build_fields(template: dict) -> dict:
    """在真实样本模板上重建动态字段（DES 字段按混淆名重新加密，时间类刷新）。"""
    now = int(time.time() * 1000)
    f = dict(template)
    f["bl"] = des_encrypt(ORG, K["bl"])
    f["xi"] = des_encrypt(APPID, K["xi"])
    f["tf"] = des_encrypt("web", K["tf"])
    f["version"] = "3.0.0"
    f["nv"] = des_encrypt("3.0.0", K["nv"])
    f["cz"] = des_encrypt("all", K["cz"])
    f["mx"] = des_encrypt("1.0.0", K["mx"])
    f["pf"] = des_encrypt(str(random.randint(3000, 8000)), K["pf"])
    f["smid"] = get_localsmid()
    f["kt"] = des_encrypt(str(uuid.uuid4()), K["kt"])
    f["iy"] = des_encrypt(str(uuid.uuid4()), K["iy"])
    f["xy"] = des_encrypt(str(now), K["xy"])
    f["pz"] = des_encrypt(str(now), K["pz"])
    f["rz"] = js_date_string()
    f["t"] = now
    f.pop("uq", None)
    f["uq"] = des_encrypt(md5_hex(canon(f)), K["uq"])
    return f


def build_request(fields: dict, uid: str | None = None):
    uid = uid or str(uuid.uuid4())
    pri = md5_hex(uid)[:16]
    ep = rsa_encrypt_b64(uid)
    data = aes_encrypt_hex(gzip_b64(fields), pri)
    body = {"appId": APPID, "organization": ORG, "ep": ep, "data": data, "os": "web",
            "encode": 5, "compress": 2}
    return uid, pri, body


HEADERS = {
    "accept": "*/*",
    "accept-language": "zh-CN,zh;q=0.9",
    "content-type": "application/json;charset=UTF-8",
    "origin": "https://chat.deepseek.com",
    "referer": "https://chat.deepseek.com/",
    "sec-ch-ua": '"Chromium";v="141", "Not?A_Brand";v="8"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"),
}


def selftest():
    obj = dict(load_template())
    uq_raw = obj.pop("uq")
    calc = md5_hex(canon(obj))
    print("[uq ] canon md5 =", calc)
    print("[uq ] re-enc    =", des_encrypt(calc, K["uq"]))
    print("[uq ] captured  =", uq_raw, "MATCH" if des_encrypt(calc, K["uq"]) == uq_raw else "MISMATCH")

    smid = get_localsmid()
    print("[smid]", smid, "len", len(smid))
    ts, rest = smid[:14], smid[14:]
    print("[smid] tail-check", rest[32 + 2:32 + 2 + 14] == md5_hex("smsk_web_" + smid[:48])[:14])

    uid = str(uuid.uuid4())
    pri = md5_hex(uid)[:16]
    txt = json.dumps(obj, ensure_ascii=False)
    enc = aes_encrypt_hex(txt, pri)
    print("[aes] roundtrip", aes_decrypt_hex(enc, pri).decode("utf-8") == txt, "len", len(enc))

    ep = rsa_encrypt_b64(uid)
    print("[rsa] ep len", len(ep))


def main():
    if "--selftest" in sys.argv:
        selftest()
        return
    template = load_template()
    fields = build_fields(template)
    uid, pri, body = build_request(fields)
    print(f"[req] uid={uid} priId={pri} data={len(body['data'])} ep={len(body['ep'])}")
    r = requests.post(API, json=body, headers=HEADERS, timeout=30)
    print("[http]", r.status_code)
    print("[resp]", r.text[:1200])
    try:
        j = r.json()
    except Exception:
        return
    dev = (j.get("detail") or {}).get("deviceId")
    if dev:
        print("[deviceId]", dev)
        print("[device_id for DeepSeek]", "B" + dev)
        out = os.path.join("work", "sm", "fp", "deviceid.json")
        json.dump({"uid": uid, "priId": pri, "deviceId": dev, "at": time.strftime("%F %T")},
                  open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("[saved]", out)


if __name__ == "__main__":
    main()
