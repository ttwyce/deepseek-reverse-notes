"""转储 dex 中所有可打印字符串（去重排序），供 grep 检索。"""
import re, zipfile, os

APK = r"F:\dshh\deepseeka\input\DeepSeek_2.7.1_apks.apk"
OUT = r"F:\dshh\deepseeka\work\dex_strings.txt"
z = zipfile.ZipFile(APK)

strs = set()
for n in z.namelist():
    if not n.endswith(".dex"):
        continue
    data = z.read(n)
    for m in re.findall(rb"[\x20-\x7e]{6,}", data):
        strs.add(m.decode("utf-8", "ignore"))

with open(OUT, "w", encoding="utf-8", errors="ignore") as f:
    for s in sorted(strs):
        f.write(s + "\n")
print("strings:", len(strs), "->", OUT)
