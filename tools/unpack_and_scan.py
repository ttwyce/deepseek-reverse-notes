"""解包 APK 并对 dex/资源做原始字节级字符串扫描（纯 Python，无需 JDK）。"""
import os, re, zipfile, sys

APK = r"F:\dshh\deepseeka\input\DeepSeek_2.7.1_apks.apk"
OUT = r"F:\dshh\deepseeka\work\apk"
RES = r"F:\dshh\deepseeka\work"
os.makedirs(OUT, exist_ok=True)

z = zipfile.ZipFile(APK)
z.extractall(OUT)
print("extracted to", OUT)

# 1) 关键结构
dex = [n for n in z.namelist() if n.endswith(".dex")]
print("\n== DEX ==")
for d in dex:
    print(f"  {z.getinfo(d).file_size:>10}  {d}")

print("\n== native libs ==")
libs = {}
for n in z.namelist():
    if n.startswith("lib/"):
        parts = n.split("/")
        if len(parts) >= 3:
            libs.setdefault(parts[1], []).append((parts[-1], z.getinfo(n).file_size))
for abi, files in libs.items():
    print(f"  [{abi}] {len(files)} files: " + ", ".join(sorted(f[0] for f in files)))

print("\n== assets (top level) ==")
tops = set()
for n in z.namelist():
    if n.startswith("assets/"):
        seg = n.split("/")
        tops.add("/".join(seg[:2]) + ("/" if len(seg) > 2 else ""))
for t in sorted(tops):
    print("  " + t)

# 2) 字节级可打印串提取
def printable_strings(data, minlen=6):
    return re.findall(rb"[\x20-\x7e]{%d,}" % minlen, data)

url_re = re.compile(rb"https?://[A-Za-z0-9\.\-_~:/?#\[\]@!$&'()*+,;=%]+")
host_re = re.compile(rb"\b[a-z0-9][a-z0-9\-\.]{2,60}\.(?:com|cn|net|io|org|ai|co|app|dev|xyz|top|me)\b")

urls, hosts = set(), set()
for n in z.namelist():
    if n.endswith(".dex"):
        data = z.read(n)
        for m in url_re.findall(data):
            urls.add(m.decode("utf-8", "ignore"))
        for m in host_re.findall(data):
            hosts.add(m.decode("utf-8", "ignore").lower())

with open(os.path.join(RES, "scan_urls.txt"), "w", encoding="utf-8") as f:
    f.write("== URLs in dex ==\n")
    for u in sorted(urls):
        f.write(u + "\n")
    f.write("\n== hosts in dex ==\n")
    for h in sorted(hosts):
        f.write(h + "\n")

print(f"\n== scan: {len(urls)} urls, {len(hosts)} hosts -> {RES}\\scan_urls.txt ==")
for u in sorted(urls)[:120]:
    print("  " + u)
