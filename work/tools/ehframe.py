"""Recover function boundaries from .eh_frame_hdr.

The 3.10 arm64 libgame.so is stripped (474 dynsyms only, no .symtab), but it
keeps a full CFI table: .eh_frame_hdr is a sorted search table of
(initial_location, fde_address) pairs, one per function. That is enough to get
a real function inventory without a decompiler.

    python work/tools/ehframe.py <libgame.so> [out.csv]
"""
import struct
import sys


def uleb(buf, i):
    shift = value = 0
    while True:
        b = buf[i]
        i += 1
        value |= (b & 0x7f) << shift
        shift += 7
        if not b & 0x80:
            return value, i


def sleb(buf, i):
    shift = value = 0
    while True:
        b = buf[i]
        i += 1
        value |= (b & 0x7f) << shift
        shift += 7
        if not b & 0x80:
            if b & 0x40:
                value -= 1 << shift
            return value, i


def read_ptr(buf, i, enc, base):
    """Decode one DW_EH_PE-encoded pointer. Returns (value, next_index)."""
    if enc == 0xff:
        return None, i
    fmt = enc & 0x0f
    if fmt == 0x00:                       # absptr
        return struct.unpack_from("<Q", buf, i)[0], i + 8
    if fmt == 0x01:                       # uleb128
        return uleb(buf, i)
    if fmt == 0x02:
        return struct.unpack_from("<H", buf, i)[0], i + 2
    if fmt == 0x03:
        return struct.unpack_from("<I", buf, i)[0], i + 4
    if fmt == 0x04:
        return struct.unpack_from("<Q", buf, i)[0], i + 8
    if fmt == 0x09:
        return sleb(buf, i)
    if fmt == 0x0a:
        return struct.unpack_from("<h", buf, i)[0], i + 2
    if fmt == 0x0b:
        return struct.unpack_from("<i", buf, i)[0], i + 4
    if fmt == 0x0c:
        return struct.unpack_from("<q", buf, i)[0], i + 8
    raise ValueError("unknown pointer format 0x%02x" % fmt)


def sections(data):
    """Minimal section table: name -> (addr, file_offset, size)."""
    shoff = struct.unpack_from("<Q", data, 0x28)[0]
    shentsize, shnum, shstrndx = struct.unpack_from("<HHH", data, 0x3a)
    raw = []
    for k in range(shnum):
        off = shoff + k * shentsize
        name, stype = struct.unpack_from("<II", data, off)
        addr, offset, size = struct.unpack_from("<QQQ", data, off + 16)
        raw.append((name, stype, addr, offset, size))
    str_off = raw[shstrndx][3]
    out = {}
    for name, stype, addr, offset, size in raw:
        end = data.index(b"\0", str_off + name)
        out[data[str_off + name:end].decode()] = (addr, offset, size)
    return out


def functions(data, secs):
    addr, off, size = secs[".eh_frame_hdr"]
    hdr = data[off:off + size]
    version = hdr[0]
    enc_ptr, enc_cnt, enc_tab = hdr[1], hdr[2], hdr[3]
    if version != 1:
        raise SystemExit("unexpected .eh_frame_hdr version %d" % version)
    i = 4
    eh_frame_ptr, i = read_ptr(hdr, i, enc_ptr, off)
    count, i = read_ptr(hdr, i, enc_cnt, off)
    table_at = i
    out = []
    for k in range(count):
        base = table_at + k * 8
        loc, _ = read_ptr(hdr, base, enc_tab, addr - off + off)   # datarel -> section vaddr
        fde, _ = read_ptr(hdr, base + 4, enc_tab, addr - off + off)
        if loc is None:
            break
        out.append(loc)
    out.sort()
    return out, count, eh_frame_ptr


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "work/libs/orig_libgame.so"
    csv = sys.argv[2] if len(sys.argv) > 2 else ""
    data = open(path, "rb").read()
    secs = sections(data)
    starts, count, eh = functions(data, secs)
    text_addr, text_off, text_size = secs[".text"]
    text_end = text_addr + text_size
    rows = []
    for k, start in enumerate(starts):
        end = starts[k + 1] if k + 1 < len(starts) else text_end
        if text_addr <= start < text_end:
            rows.append((start, end - start))
    print("eh_frame_hdr entries : %d" % count)
    print("decoded              : %d" % len(starts))
    print("functions in .text   : %d" % len(rows))
    if rows:
        sizes = sorted(r[1] for r in rows)
        print("size  min/median/max : %d / %d / %d" % (sizes[0], sizes[len(sizes) // 2], sizes[-1]))
        print("text coverage        : %.1f%%" % (100.0 * sum(r[1] for r in rows) / text_size))
    if csv:
        with open(csv, "w", encoding="utf-8") as f:
            f.write("addr,size\n")
            for a, s in rows:
                f.write("0x%x,%d\n" % (a, s))
        print("wrote " + csv)


if __name__ == "__main__":
    main()
