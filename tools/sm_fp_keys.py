"""穷举数美指纹字段的「混淆名 key」：对每个 base64 字段用候选 8 字符 key 做 DES-ECB 解密。

产出 work/sm/fp/field_keys.json，映射 字段名 -> {key, plain}。
"""
import base64
import json
import re
import warnings

from cryptography.hazmat.primitives.ciphers import Cipher, modes

try:
    from cryptography.hazmat.decrepit.ciphers.algorithms import TripleDES
except Exception:  # pragma: no cover
    from cryptography.hazmat.primitives.ciphers.algorithms import TripleDES

warnings.filterwarnings("ignore")

PRETTY = r"work\sm\fp.min.pretty.js"
PLAIN = r"work\sm\fp\plain.json"
OUT = r"work\sm\fp\field_keys.json"


def des_decrypt(key: str, data: bytes) -> bytes:
    k = key.encode()
    c = Cipher(TripleDES(k * 3), modes.ECB())
    d = c.decryptor()
    return (d.update(data) + d.finalize()).rstrip(b"\x00")


def score(raw: bytes):
    """明文合理性打分：可 UTF-8 解码 + 可打印比例。"""
    try:
        txt = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None, -1.0
    if not txt:
        return txt, -1.0
    good = sum(1 for ch in txt if ch.isprintable() or ch in "\n\t")
    return txt, good / len(txt)


def main():
    src = open(PRETTY, encoding="utf-8").read()
    cands = set(m.group(1) for m in re.finditer(r"'([a-z0-9]{8})'", src))
    # 数美混淆名也可能是 7/9 位，再补一轮
    cands |= set(m.group(1) for m in re.finditer(r"'([a-z0-9]{7,9})'", src))
    cands = sorted(cands)
    print(f"[cands] {len(cands)} 个候选 key")

    plain = json.load(open(PLAIN, encoding="utf-8"))[0]["str"]
    obj = json.loads(plain)

    result = {}
    for field, val in obj.items():
        if not isinstance(val, str) or len(val) < 12:
            continue
        try:
            raw = base64.b64decode(val, validate=True)
        except Exception:
            continue
        if len(raw) % 8 or not raw:
            continue
        best = None
        for key in cands:
            if len(key.encode()) != 8:
                continue
            try:
                plain_bytes = des_decrypt(key, raw)
            except Exception:
                continue
            txt, sc = score(plain_bytes)
            if sc > 0.95 and (best is None or sc > best[2]):
                best = (key, txt, sc)
        if best:
            result[field] = {"key": best[0], "plain": best[1], "score": round(best[2], 3)}

    json.dump(result, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"[hit] {len(result)}/{sum(1 for v in obj.values() if isinstance(v, str))} 字段解出")
    for k, v in result.items():
        print(f"  {k:>16}  key={v['key']:<10} plain={v['plain'][:120]!r}")

    miss = [k for k, v in obj.items() if isinstance(v, str) and len(v) >= 12 and k not in result]
    print("[未解出]", miss)


if __name__ == "__main__":
    main()
