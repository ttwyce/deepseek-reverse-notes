import json, re, base64
st = json.load(open(r"work\pw_storage.json", encoding="utf-8"))
target = "BNaTEWNfiFMdnqIEm6bgYReu82v3DlNH+eFGqTXHGyRxbMKwiK2W2QmI9jXc3qdDhyPjyUerU43GzO70hgtlu3g=="
print("== localStorage keys ==")
for k, v in st.items():
    print(f"  {k} = {str(v)[:160]}")
print("\n== contains target? ==", any(target in str(v) for v in st.values()))
# 解密 thumbcache 看是否 64 字节
for k, v in st.items():
    if "thumbcache" in k or "did" in k.lower():
        print(f"\n{k}: len={len(str(v))} val={str(v)[:120]}")
