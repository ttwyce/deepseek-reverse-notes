import re
src = open(r"F:\dshh\deepseeka\work\web_main.js", encoding="utf-8", errors="replace").read()
i = src.find('7586(e,t,n)')
print("idx", i)
print(src[i:i+2600])
