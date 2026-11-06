"""ARM64 反汇编工具：给定 .so 与 vaddr，输出反汇编，并递归展开 bl 目标。

用法: python tools\disas.py <so> <vaddr_hex> [size_hex] [--calls]
"""
import sys, struct
sys.stdout.reconfigure(encoding="utf-8")
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from elftools.elf.elffile import ELFFile

so = sys.argv[1]
start = int(sys.argv[2], 16)
size = int(sys.argv[3], 16) if len(sys.argv) > 3 and not sys.argv[3].startswith("--") else 0x400
expand_calls = "--calls" in sys.argv

f = open(so, "rb")
elf = ELFFile(f)

def v2o(addr):
    for seg in elf.iter_segments():
        if seg["p_type"] == "PT_LOAD":
            a, sz, off = seg["p_vaddr"], seg["p_filesz"], seg["p_offset"]
            if a <= addr < a + sz:
                return off + (addr - a)
    return None

def o2v(addr):
    for seg in elf.iter_segments():
        if seg["p_type"] == "PT_LOAD":
            a, sz, off = seg["p_vaddr"], seg["p_filesz"], seg["p_offset"]
            if off <= addr < off + sz:
                return a + (addr - off)
    return None

md = Cs(CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN)
md.detail = True

def disas(addr, nbytes, label=""):
    off = v2o(addr)
    if off is None:
        print(f"  !! cannot map {addr:#x}")
        return []
    f.seek(off)
    code = f.read(nbytes)
    out = []
    print(f"\n===== {label} @ {addr:#x} ({nbytes:#x} bytes) =====")
    for ins in md.disasm(code, addr):
        line = f"  {ins.address:#08x}  {ins.bytes.hex():<10} {ins.mnemonic:<8} {ins.op_str}"
        print(line)
        out.append(ins)
    return out

insns = disas(start, size, "target")

if expand_calls:
    seen = set()
    targets = []
    for ins in insns:
        if ins.mnemonic in ("bl", "b") and ins.op_str.startswith("#"):
            try:
                t = int(ins.op_str[1:], 16)
            except ValueError:
                continue
            if t not in seen and t != start:
                seen.add(t)
                targets.append(t)
    for t in targets[:12]:
        # 猜函数长度：到下一个函数或 0x200
        disas(t, 0x180, f"callee from {start:#x}")
