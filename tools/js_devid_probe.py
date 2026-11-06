import re
src = open(r"work\web_main.js", encoding="utf-8", errors="replace").read()
for kw in ["smidV2", "deviceId:", "deviceId=", "getDeviceId", "device_id:", "deviceProfile", "deviceprofile"]:
    idxs = [m.start() for m in re.finditer(re.escape(kw), src)]
    print(f"--- {kw}: {len(idxs)} hits {idxs[:12]}")
