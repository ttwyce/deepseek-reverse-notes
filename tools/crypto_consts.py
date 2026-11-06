"""在 .so 中搜索已知密码学常量，并列出目标函数范围内的 bl 调用目标。"""
import sys, struct
sys.stdout.reconfigure(encoding="utf-8")
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from elftools.elf.elffile import ELFFile

so = sys.argv[1]
start = int(sys.argv[2], 16)
size = int(sys.argv[3], 16)
data = open(so, "rb").read()
elf = ELFFile(open(so, "rb"))

# --- 1. 常量搜索 ---
CONSTS = {
    0x6A09E667: "SHA256 H0", 0xBB67AE85: "SHA256 H1", 0x3C6EF372: "SHA256 H2",
    0xA54FF53A: "SHA256 H3", 0x510E527F: "SHA256 H4", 0x9B05688C: "SHA256 H5",
    0x1F83D9AB: "SHA256 H6", 0x5BE0CD19: "SHA256 H7",
    0x428A2F98: "SHA256 K0", 0x71374491: "SHA256 K1", 0xB5C0FBCF: "SHA256 K2",
    0xCBF29CE484222325: "FNV-1a 64 offset",
    0x6A09E667F3BCC908: "SHA512 H0",
    0x243F6A8885A308D3: "BLAKE2/Argon iv0",
    0x9E3779B97F4A7C15: "golden ratio 64",
    0x5BD1E995: "MurmurHash2 mix",
    0x85EBCA6B: "Murmur3 c1", 0xC2B2AE35: "Murmur3 c2",
    0xFF51AFD7ED558CCD: "Murmur/xx c1", 0xC4CEB9FE1A85EC53: "Murmur c2",
    0x9E3779B1: "golden ratio 32",
}
print("=== 32/64 位常量搜索（全文件）===")
for val, name in CONSTS.items():
    if val <= 0xFFFFFFFF:
        pat = struct.pack("<I", val)
    else:
        pat = struct.pack("<Q", val)
    idx = 0
    found = []
    while True:
        i = data.find(pat, idx)
        if i < 0:
            break
        found.append(i)
        idx = i + 1
        if len(found) > 8:
            break
    if found:
        print(f"  {name:<22} {val:#x} @ " + ", ".join(f"{x:#x}" for x in found))

# --- 2. bl 调用目标统计 ---
def v2o(addr):
    for seg in elf.iter_segments():
        if seg["p_type"] == "PT_LOAD":
            a, sz, off = seg["p_vaddr"], seg["p_filesz"], seg["p_offset"]
            if a <= addr < a + sz:
                return off + (addr - a)
    return None

off = v2o(start)
code = data[off:off + size]
md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
import collections
calls = collections.Counter()
for ins in md.disasm(code, start):
    if ins.mnemonic == "bl" and ins.op_str.startswith("#"):
        calls[int(ins.op_str[1:], 16)] += 1
print(f"\n=== {start:#x}..{start+size:#x} 内 bl 目标（{sum(calls.values())} 次）===")
for t, c in sorted(calls.items()):
    print(f"  {t:#08x}  x{c}")
