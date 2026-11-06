import re
src = open(r"F:\dshh\deepseeka\work\web_main.js", encoding="utf-8", errors="replace").read()
print("len", len(src))
for pat in ["users/login", "turnstile", "create_guest_challenge", "device_id", "x-request-encryption-key", "PoW", "challenge"]:
    hits = [m.start() for m in re.finditer(re.escape(pat), src)]
    print(f"--- {pat}: {len(hits)}")
    for h in hits[:4]:
        print("   ...", src[max(0,h-160):h+200].replace("\n"," "))
