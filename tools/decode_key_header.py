import base64, json
k = "I0qMdnnhEo8l8S/yBYvLsE/eRHXH1Cs0JG8P4O25uJ2wwxsVN3CIYRGPehIxRWW8OE6Pp5k2YhrjVsZMWAyf49e/rZlqD/mxCj2WgQYhsa2v+2AABfaZsIQ3"
print("b64 len:", len(k))
raw = base64.b64decode(k)
print("raw len:", len(raw))
print("hex:", raw.hex())
d = json.load(open(r"work\pw_login_request.json", encoding="utf-8"))[0]
b = base64.b64decode(d["body_b64"])
print("body len:", len(b))
print("body hex:", b.hex()[:200])
