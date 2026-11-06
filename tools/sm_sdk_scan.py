"""静态扫描 captcha-sdk.min.js：定位 verify 构造、加密实现、参数编码。"""
import re
import sys

SRC = r"work\sm\captcha-sdk.min.js"
s = open(SRC, encoding="utf-8", errors="replace").read()
print(f"[size] {len(s)} 单行数={s.count(chr(10))+1}")

KEYS = [
    "fverify", "fVerify", "verify", "encrypt", "decrypt", "AES", "aes", "CBC", "Pkcs7", "pkcs7",
    "base64", "Base64", "atob", "btoa", "Utf8", "toString(16)", "createCipher", "createDecipher",
    "CryptoJS", "JSEncrypt", "RSA", "publicKey", "sm2", "sm4",
    "captchaUuid", "riskLevel", "track", "rid", "spatial", "clickPoints", "coordinates",
]


def show(pat, ctx=260, limit=8):
    hits = [m.start() for m in re.finditer(re.escape(pat), s)]
    print(f"\n########## {pat}  命中 {len(hits)} 处 ##########")
    for i, pos in enumerate(hits[:limit]):
        seg = s[max(0, pos - ctx): pos + ctx].replace("\n", "\\n")
        print(f"--- #{i} @{pos} ---\n{seg}\n")


for k in KEYS:
    show(k)

# 找所有 /ca/ 路径字符串
print("\n########## /ca/ 路径 ##########")
for m in set(re.findall(r"['\"]/(?:ca|pr|crb)/[A-Za-z0-9_./-]{2,60}['\"]", s)):
    print(" ", m)
