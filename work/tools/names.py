"""Guess what a stripped function does from the .rodata strings it touches.

Disassembles a function with capstone and resolves ADRP+ADD pairs that land in
.rodata; the referenced literals usually name the subsystem (log tag, dvar name,
asset path, error message).

    python work/tools/names.py <libgame.so> <vaddr>[,<vaddr>...]
"""
import bisect
import struct
import sys

from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM


def sections(data):
    shoff = struct.unpack_from("<Q", data, 0x28)[0]
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 0x3a)
    raw = [struct.unpack_from("<IIQQQQ", data, shoff + k * shentsize) for k in range(shnum)]
    str_off = raw[shstrndx][4]
    out = {}
    for name, stype, flags, addr, offset, size in raw:
        end = data.index(b"\0", str_off + name)
        out[data[str_off + name:end].decode()] = (addr, offset, size)
    return out


def fn_table(csv):
    starts, sizes = [], []
    for line in open(csv, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("addr"):
            continue
        a, s = line.split(",")
        starts.append(int(a, 16))
        sizes.append(int(s))
    return starts, sizes


def cstr(data, secs, vaddr):
    for name, (addr, off, size) in secs.items():
        if addr <= vaddr < addr + size and name not in (".text",):
            start = off + (vaddr - addr)
            try:
                end = data.index(b"\0", start, min(start + 200, len(data)))
            except ValueError:
                return None
            if end - start > 120:
                return None
            raw = data[start:end]
            if len(raw) >= 4 and all(32 <= b < 127 or b in (9, 10) for b in raw):
                return raw.decode("ascii", "replace")
    return None


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "work/libs/orig_libgame.so"
    addrs = [int(a, 16) for a in (sys.argv[2] if len(sys.argv) > 2 else "0x47ded18").split(",")]
    data = open(path, "rb").read()
    secs = sections(data)
    starts, sizes = fn_table("work/analysis/functions_310.csv")
    text_addr, text_off, text_size = secs[".text"]
    md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
    md.detail = True
    for target in addrs:
        idx = bisect.bisect_right(starts, target) - 1
        start = starts[idx] if idx >= 0 else target
        size = sizes[idx] if idx >= 0 else 256
        end = min(start + size, target + 4096)
        code = data[text_off + (start - text_addr): text_off + (end - text_addr)]
        pages = {}
        seen = []
        for insn in md.disasm(code, start):
            m = insn.mnemonic
            if m == "adrp" and insn.operands:
                dr = insn.reg_name(insn.operands[0].reg)
                pages[dr] = insn.operands[1].imm
            elif m == "add" and len(insn.operands) == 3:
                dst = insn.reg_name(insn.operands[0].reg)
                src = insn.reg_name(insn.operands[1].reg)
                if src in pages and insn.operands[2].type == 2:
                    s = cstr(data, secs, pages[src] + insn.operands[2].imm)
                    if s and s not in seen:
                        seen.append(s)
        print("== 0x%x (fn 0x%x size %d) strings=%d" % (target, start, size, len(seen)))
        for s in seen[:14]:
            print("   ", repr(s[:90]))


if __name__ == "__main__":
    main()
