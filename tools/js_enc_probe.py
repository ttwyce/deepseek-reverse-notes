import re
src = open(r"work\web_main.js", encoding="utf-8", errors="replace").read()
print("len:", len(src))
for kw in ["x-request-encryption-key", "request-encryption", "OAEP", "RSA-OAEP", "subtle.encrypt", "importKey", "AES-CBC", "AES-GCM", "spki"]:
    idxs = [m.start() for m in re.finditer(re.escape(kw), src)]
    print(f"{kw}: {len(idxs)} hits at {idxs[:8]}")
