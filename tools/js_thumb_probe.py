import re
for fn in ["work\\web_main.js", "work\\web_vendors.js"]:
    src = open(fn, encoding="utf-8", errors="replace").read()
    print(f"===== {fn} len={len(src)}")
    for kw in ["thumbcache", "thumbCache", "smidV2", "fengkongcloud", "deviceprofile"]:
        idxs = [m.start() for m in re.finditer(re.escape(kw), src)]
        print(f"  {kw}: {len(idxs)} {idxs[:10]}")
