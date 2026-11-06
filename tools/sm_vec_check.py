"""用 work/sm/vectors.json 全量校验 sm_crypto.encrypt。"""
import json
import sys

sys.path.insert(0, r"tools")
from sm_crypto import encrypt  # noqa: E402

vec = json.load(open(r"work\sm\vectors.json", encoding="utf-8"))
bad = 0
for c in vec:
    if c.get("err"):
        continue
    got = encrypt(c["val"], c["salt"])
    if got != c["b64"]:
        bad += 1
        if bad <= 15:
            print(f"MISMATCH salt={c['salt']} val={c['val']!r} js={c['b64']} py={got}")
print(f"total={len(vec)} checked={sum(1 for c in vec if not c.get('err'))} bad={bad}")
