"""验证数美指纹的 uq 签名算法（md5 of 递归规范化字符串）。"""
import hashlib
import json

PLAIN = r"work\sm\fp\plain.json"


def canon(x) -> str:
    if isinstance(x, dict):
        parts = []
        for k in sorted(x.keys()):
            v = x[k]
            if isinstance(v, bool):
                parts.append("true" if v else "false")
            elif isinstance(v, (int, float)):
                num = 10000 * v
                parts.append(canon_num(num))
            elif isinstance(v, str):
                parts.append(canon(v))
            else:
                parts.append(canon(v))
        return "".join(parts)
    if isinstance(x, list):
        out = []
        for v in x:
            if isinstance(v, dict):
                out.append("[object Object]")
            elif isinstance(v, bool):
                out.append("true" if v else "false")
            elif v is None:
                out.append("null")
            else:
                out.append(str(v) if not isinstance(v, float) else canon_num(v))
        return ",".join(out)
    if isinstance(x, str):
        return x if x else ""
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, (int, float)):
        return canon_num(10000 * x)
    if x is None:
        return ""
    return str(x)


def canon_num(n) -> str:
    """模拟 JS Number.toString：整数无小数点，浮点用最短表示。"""
    if isinstance(n, float) and n.is_integer() and abs(n) < 1e21:
        return str(int(n))
    if isinstance(n, float):
        r = repr(n)
        return r
    return str(n)


def main():
    obj = json.loads(json.load(open(PLAIN, encoding="utf-8"))[0]["str"])
    target = obj.pop("uq")
    s = canon(obj)
    got = hashlib.md5(s.encode("utf-8")).hexdigest()
    print("canon len:", len(s))
    print("canon head:", s[:200])
    print("canon tail:", s[-300:])
    print("target uq:", target)
    print("computed :", got, "MATCH" if got == target else "MISMATCH")


if __name__ == "__main__":
    main()
