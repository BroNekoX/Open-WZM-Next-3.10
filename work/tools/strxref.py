"""Index .rodata string references in the stripped libgame.so.

One linear pass over .text decoding ADRP + ADD pairs: ADRP forms a page, ADD adds
the low 12 bits, the result is a .rodata address. A string referenced this way is
usually the log tag / dvar name / asset path that names the function around it.

    python work/tools/strxref.py <libgame.so> <out.csv>

CSV: string_addr,string,func_addr
"""
import bisect
import struct
import sys


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


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "work/libs/orig_libgame.so"
    out_csv = sys.argv[2] if len(sys.argv) > 2 else "work/analysis/string_xrefs_310.csv"
    data = open(path, "rb").read()
    secs = sections(data)
    text_addr, text_off, text_size = secs[".text"]
    ro_addr, ro_off, ro_size = secs[".rodata"]
    ro_end = ro_addr + ro_size
    starts = sorted(int(l.split(",")[0], 16) for l in open("work/analysis/functions_310.csv", encoding="utf-8")
                    if l.strip() and not l.startswith("addr"))
    words = struct.unpack_from("<%dI" % (text_size // 4), data, text_off)
    page_reg = {}
    rows = 0
    seen = set()
    with open(out_csv, "w", encoding="utf-8") as f:
        f.write("string_addr,string,func_addr\n")
        for k, w in enumerate(words):
            pc = text_addr + k * 4
            if (w & 0x9F00001F) == 0x90000000:                    # ADRP
                rd = w & 0x1F
                imm = ((w >> 5) & 0x7FFFF) << 2 | ((w >> 29) & 0x3)
                imm = (imm ^ 0x100000) - 0x100000 if imm & 0x100000 else imm
                page_reg[rd] = (pc & ~0xFFF) + (imm << 12)
                continue
            if (w & 0xFF800000) == 0x91000000:                    # ADD (immediate)
                rd = w & 0x1F
                rn = (w >> 5) & 0x1F
                imm12 = (w >> 10) & 0xFFF
                page = page_reg.get(rn)
                if page is None:
                    continue
                target = page + imm12
                if not (ro_addr <= target < ro_end):
                    continue
                if target in seen:
                    continue
                off = ro_off + (target - ro_addr)
                try:
                    end = data.index(b"\0", off, min(off + 120, len(data)))
                except ValueError:
                    continue
                raw = data[off:end]
                if len(raw) < 4 or not all(32 <= b < 127 for b in raw):
                    continue
                seen.add(target)
                idx = bisect.bisect_right(starts, pc) - 1
                func = starts[idx] if idx >= 0 else 0
                f.write("0x%x,%s,0x%x\n" % (target, '"' + raw.decode("ascii") + '"', func))
                rows += 1
    print("strings indexed:", rows)


if __name__ == "__main__":
    main()
