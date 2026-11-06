"""用 Unicorn 模拟 librscrypto.so 的 0x19bc0（PoW 求解核心），验证 base 格式。"""
import struct
import sys

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm64_const import (
    UC_ARM64_REG_SP,
    UC_ARM64_REG_X0,
    UC_ARM64_REG_X1,
    UC_ARM64_REG_X2,
    UC_ARM64_REG_X3,
    UC_ARM64_REG_X4,
    UC_ARM64_REG_LR,
    UC_ARM64_REG_PC,
)

SO = r"F:\dshh\deepseeka\work\apk\lib\arm64-v8a\librscrypto.so"
FN = 0x19BC0
STACK = 0x10000000
STACK_SZ = 0x200000
HEAP = 0x20000000
HEAP_SZ = 0x400000
SENTINEL = 0x30000000


def build():
    uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
    with open(SO, "rb") as f:
        elf = ELFFile(f)
        for seg in elf.iter_segments():
            if seg.header.p_type != "PT_LOAD":
                continue
            va = seg.header.p_vaddr
            memsz = seg.header.p_memsz
            data = seg.data()
            base = va & ~0xFFF
            size = ((va + memsz - base) + 0xFFF) & ~0xFFF
            try:
                uc.mem_map(base, size, 7)
            except Exception:  # noqa: BLE001
                pass
            if data:
                uc.mem_write(va, data)
    uc.mem_map(STACK, STACK_SZ, 7)
    uc.mem_map(HEAP, HEAP_SZ, 7)
    uc.mem_map(SENTINEL, 0x1000, 7)
    return uc


def run(base_str: str, challenge_hex: str, difficulty: int, trace=False):
    uc = build()
    b = base_str.encode()
    uc.mem_write(HEAP, b)
    uc.mem_write(HEAP + 0x1000, challenge_hex.encode())
    uc.reg_write(UC_ARM64_REG_X0, HEAP + 0x1000)
    uc.reg_write(UC_ARM64_REG_X1, len(challenge_hex))
    uc.reg_write(UC_ARM64_REG_X2, HEAP)
    uc.reg_write(UC_ARM64_REG_X3, len(b))
    uc.reg_write(UC_ARM64_REG_X4, difficulty)
    uc.reg_write(UC_ARM64_REG_SP, STACK + STACK_SZ - 0x1000)
    uc.reg_write(UC_ARM64_REG_LR, SENTINEL)

    if trace:
        count = [0]

        def hook(uc_, addr, size, _):
            count[0] += 1
            if count[0] < 40:
                print(f"    pc=0x{addr:x}")

        uc.hook_add(UC_HOOK_CODE, hook)

    try:
        uc.emu_start(FN, SENTINEL, timeout=60 * 1000 * 1000, count=200_000_000)
    except Exception as e:  # noqa: BLE001
        return f"EXC {type(e).__name__}: {e} (pc=0x{uc.reg_read(UC_ARM64_REG_PC):x})"
    return uc.reg_read(UC_ARM64_REG_X0)


if __name__ == "__main__":
    salt = "0f4825ab243668067c02"
    ch = "b97657f833a4a3f7dd54da8af25056b8d9b4f33b31fd01bf743f186a70fa28d5"
    exp = 1792936846474
    cands = [
        f"{salt}_{exp}_",
        f"{salt}_{exp}",
        f"{salt}_",
        salt,
        f"{exp}_{salt}_",
    ]
    for c in cands:
        r = run(c, ch, 20)
        print(f"base={c!r:32s} -> {r}")
    print("--- trace first case ---")
    run(f"{salt}_{exp}_", ch, 20, trace=True)
    sys.exit(0)
