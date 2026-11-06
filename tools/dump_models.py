"""从 jadx 反编译源码中提取 kotlinx.serialization 模型定义（类名 + 字段序列）。

R8 混淆后每个 @Serializable 类都有形如:
    di8 di8Var = new di8("com.deepseek.chat.network.xxx.Foo", ...);
    di8Var.j("fieldName", isOptional);
的 descriptor 构造，字段顺序即 JSON 字段顺序。
"""
import os, re, sys, json

sys.stdout.reconfigure(encoding="utf-8")
SRC = r"F:\dshh\deepseeka\work\jadx_out\sources"

rx_new = re.compile(r'new\s+di8\(\s*"([^"]+)"')
rx_field = re.compile(r'di8\.j\(\s*"([^"]+)"\s*,\s*(true|false)\s*\)')
rx_anyfield = re.compile(r'\.j\(\s*"([A-Za-z0-9_\-\.]+)"\s*,\s*(true|false)\s*\)')

models = {}

for dirpath, dirnames, filenames in os.walk(SRC):
    for fn in filenames:
        if not fn.endswith(".java"):
            continue
        p = os.path.join(dirpath, fn)
        try:
            txt = open(p, encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        m = rx_new.search(txt)
        if not m:
            continue
        cls = m.group(1)
        fields = []
        for fm in rx_anyfield.finditer(txt):
            fields.append((fm.group(1), fm.group(2) == "true"))
        models.setdefault(cls, {"file": p[len(SRC) + 1:], "fields": []})
        if len(fields) > len(models[cls]["fields"]):
            models[cls]["fields"] = fields
        models[cls].setdefault("files", set()).add(p[len(SRC) + 1:])

# 输出
out = []
for cls in sorted(models):
    v = models[cls]
    out.append(cls)
    out.append("    file: " + v["file"])
    if v["fields"]:
        out.append("    fields: " + ", ".join(f + ("?" if o else "") for f, o in v["fields"]))
    out.append("")

open(r"F:\dshh\deepseeka\work\models_dump.txt", "w", encoding="utf-8").write("\n".join(out))
print(f"models found: {len(models)}  -> work\\models_dump.txt")
# 只打印 network 相关
n = 0
for cls in sorted(models):
    if ".network." in cls or "deepseek" in cls:
        v = models[cls]
        print(cls)
        print("    " + ", ".join(f + ("?" if o else "") for f, o in v["fields"]))
        n += 1
print("network-related:", n)
