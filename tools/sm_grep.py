import sys

s = open(r"work\sm\captcha-sdk.deob.js", encoding="utf-8", errors="replace").read()
needle = sys.argv[1]
width = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
start = 0
count = 0
while True:
    i = s.find(needle, start)
    if i < 0:
        break
    count += 1
    print(f"=== hit {count} @ {i} ===")
    print(s[i : i + width])
    print()
    start = i + 1
    if count >= int(sys.argv[3] if len(sys.argv) > 3 else 3):
        break
print("total shown:", count)
