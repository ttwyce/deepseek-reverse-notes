import sys, zipfile, os

path = sys.argv[1] if len(sys.argv) > 1 else r"F:\dshh\deepseeka\input\DeepSeek_2.7.1_apks.apk"
z = zipfile.ZipFile(path)
infos = z.infolist()
print("entries:", len(infos))
total = 0
for i in infos:
    total += i.file_size
    print(f"{i.file_size:>12}  {i.filename}")
print("total uncompressed:", total)
