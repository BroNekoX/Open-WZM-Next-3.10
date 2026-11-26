"""Direct-call cross references for the 3.10 arm64 libgame.so.

Stripped binary, so callers are recovered by decoding BL (opcode 0x94xxxxxx,
imm26 -> >>2, sign extended, pc relative). Linear scanning of .text is exact for
direct calls; indirect calls (BLR) are not resolved here.

    python work/tools/xrefs.py <libgame.so> <targets.txt>

targets.txt holds one hex vaddr per line. Prints, per target, the calling
functions (resolved through work/analysis/functions_310.csv when present).
"""
import bisect
import struct
import sys


def load_functions(csv):
    starts = []
    for line in open(csv, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("addr"):
            continue
        a = int(line.split(",")[0], 16)
        starts.append(a)
    starts.sort()
    return starts


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
    tpath = sys.argv[2] if len(sys.argv) > 2 else "work/analysis/targets.txt"
    data = open(path, "rb").read()
    secs = sections(data)
    starts = load_functions("work/analysis/functions_310.csv")
    text_addr, text_off, text_size = secs[".text"]
    targets = {}
    for line in open(tpath, encoding="utf-8"):
        line = line.strip().split("#")[0].strip()
        if line:
            targets[int(line, 16)] = []
    words = struct.unpack_from("<%dI" % (text_size // 4), data, text_off)
    for k, w in enumerate(words):
        if (w & 0xFC000000) != 0x94000000:
            continue
        pc = text_addr + k * 4
        imm = w & 0x03FFFFFF
        if imm & 0x02000000:
            imm -= 0x04000000
        target = pc + (imm << 2)
        if target in targets:
            idx = bisect.bisect_right(starts, pc) - 1
            caller = starts[idx] if idx >= 0 else 0
            targets[target].append(caller)
    for target in sorted(targets):
        callers = sorted(set(targets[target]))
        print("0x%x  callers=%d" % (target, len(callers)))
        for c in callers[:12]:
            print("    from 0x%x" % c)


if __name__ == "__main__":
    main()
