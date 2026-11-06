"""轻量 ELF64 解析：列出动态符号/字符串，定位指定 JNI 函数。"""
import sys, struct

sys.stdout.reconfigure(encoding="utf-8")

def parse(path):
    data = open(path, "rb").read()
    assert data[:4] == b"\x7fELF", "not ELF"
    is64 = data[4] == 2
    assert is64, "只支持 ELF64"
    le = data[5] == 1
    e = "<" if le else ">"
    e_shoff, = struct.unpack_from(e + "Q", data, 0x28)
    e_shentsize, e_shnum, e_shstrndx = struct.unpack_from(e + "HHH", data, 0x3A)
    secs = []
    for i in range(e_shnum):
        off = e_shoff + i * e_shentsize
        name, typ, flags, addr, offset, size, link, info, align, entsize = struct.unpack_from(
            e + "IIQQQQIIQQ", data, off)
        secs.append(dict(name=name, typ=typ, flags=flags, addr=addr, off=offset,
                         size=size, link=link, info=info, entsize=entsize))
    shstr = secs[e_shstrndx]
    shstrtab = data[shstr["off"]:shstr["off"] + shstr["size"]]
    def nm(o):
        end = shstrtab.find(b"\0", o)
        return shstrtab[o:end].decode("utf-8", "replace")
    for s in secs:
        s["sname"] = nm(s["name"])
    return data, secs, e

def getsyms(data, secs, e):
    out = []
    for s in secs:
        if s["typ"] not in (2, 11):  # SYMTAB, DYNSYM
            continue
        strtab = secs[s["link"]]
        st = data[strtab["off"]:strtab["off"] + strtab["size"]]
        n = s["size"] // 24
        for i in range(n):
            nameoff, info, other, shndx, value, size = struct.unpack_from(
                e + "IBBHQQ", data, s["off"] + i * 24)
            if nameoff == 0:
                continue
            end = st.find(b"\0", nameoff)
            name = st[nameoff:end].decode("utf-8", "replace")
            out.append((name, value, size, info & 0xf, s["sname"]))
    return out

path = sys.argv[1] if len(sys.argv) > 1 else r"F:\dshh\deepseeka\work\apk\lib\arm64-v8a\librscrypto.so"
data, secs, e = parse(path)
print(f"file: {path}  size={len(data)}")
print("sections:", ", ".join(f"{s['sname']}({s['size']:#x})" for s in secs if s["sname"]))
syms = getsyms(data, secs, e)
print(f"\nsymbols: {len(syms)}")
funcs = [s for s in syms if s[3] == 2 and s[1] != 0]
print(f"FUNC symbols (global/defined): {len(funcs)}")
for name, value, size, _, tab in sorted(funcs, key=lambda x: x[1]):
    print(f"  {value:#010x} size={size:#08x} {name}  [{tab}]")
print("\n=== 含 crypto/pow 关键字的符号 ===")
for name, value, size, typ, tab in syms:
    ln = name.lower()
    if any(k in ln for k in ("pow", "hash", "crypt", "java_", "jni", "sha", "md5", "aes", "rsa")):
        print(f"  {value:#010x} size={size:#08x} type={typ} {name}")
