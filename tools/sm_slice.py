"""按偏移打印 deob SDK 片段。用法: python tools/sm_slice.py <offset> [len]"""
import sys

s = open(r"work\sm\captcha-sdk.deob.js", encoding="utf-8", errors="replace").read()
off = int(sys.argv[1])
n = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
print(s[off : off + n])
