"""分析 native 库：导出符号（Java_/JNI/crypto 特征）。"""
import re, sys, struct

sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"F:\dshh\deepseeka\work\apk\lib\arm64-v8a"

import os
targets = [f for f in os.listdir(ROOT) if f.endswith(".so")]
targets.sort(key=lambda f: -os.path.getsize(os.path.join(ROOT, f)))

for f in targets:
    p = os.path.join(ROOT, f)
    size = os.path.getsize(p)
    data = open(p, "rb").read()
    strs = set(re.findall(rb"[\x20-\x7e]{4,}", data))
    jni = sorted(s.decode() for s in strs if b"Java_" in s)
    interest = sorted(s.decode() for s in strs
                      if re.search(rb"(?i)(aes|rsa|hmac|sha256|encrypt|decrypt|sign|rscrypto|pow|ds_|deepseek|token|hif|sm[234]|md5)", s)
                      and len(s) < 120)
    print("=" * 70)
    print(f"{f}  ({size} bytes)  jni_syms={len(jni)}  interesting={len(interest)}")
    for j in jni[:40]:
        print("  JNI  " + j)
    for i in interest[:60]:
        print("  STR  " + i)
