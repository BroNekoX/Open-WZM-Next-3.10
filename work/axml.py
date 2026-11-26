"""Minimal Android binary XML (AXML) decoder -> text XML."""
import struct, sys

RES_STRING_POOL_TYPE = 0x0001
RES_XML_TYPE = 0x0003
RES_XML_START_NAMESPACE = 0x0100
RES_XML_END_NAMESPACE = 0x0101
RES_XML_START_ELEMENT = 0x0102
RES_XML_END_ELEMENT = 0x0103
RES_XML_CDATA = 0x0104
RES_XML_RESOURCE_MAP = 0x0180

TYPES = {
    0x00: "null", 0x01: "ref", 0x02: "attribute", 0x03: "string",
    0x04: "float", 0x05: "dimension", 0x06: "fraction",
    0x10: "int_dec", 0x11: "int_hex", 0x12: "int_boolean",
    0x1c: "int_color_argb8", 0x1f: "int_color_rgb8",
}

def read_string_pool(data, off):
    hdr = struct.unpack_from("<HHI", data, off)
    _, hdr_size, size = hdr
    count, style_count, flags, strings_start, styles_start = struct.unpack_from("<IIIII", data, off + 8)
    utf8 = bool(flags & 0x100)
    offsets = struct.unpack_from("<%dI" % count, data, off + hdr_size)
    base = off + strings_start
    out = []
    for o in offsets:
        p = base + o
        if utf8:
            # u16 len (chars), u16 len (bytes), then bytes
            n1 = data[p]; p += 1
            if n1 & 0x80:
                n1 = ((n1 & 0x7f) << 8) | data[p]; p += 1
            n2 = data[p]; p += 1
            if n2 & 0x80:
                n2 = ((n2 & 0x7f) << 8) | data[p]; p += 1
            out.append(data[p:p + n2].decode("utf-8", "replace"))
        else:
            n = struct.unpack_from("<H", data, p)[0]; p += 2
            if n & 0x8000:
                n = ((n & 0x7fff) << 16) | struct.unpack_from("<H", data, p)[0]; p += 2
            out.append(data[p:p + n * 2].decode("utf-16-le", "replace"))
    return out

def decode(data):
    typ, hdr_size, total = struct.unpack_from("<HHI", data, 0)
    assert typ == RES_XML_TYPE, hex(typ)
    strings = []
    res_ids = []
    out = []
    depth = 0
    off = hdr_size
    while off < total:
        ctype, chdr, csize = struct.unpack_from("<HHI", data, off)
        if csize == 0:
            break
        if ctype == RES_STRING_POOL_TYPE:
            strings = read_string_pool(data, off)
        elif ctype == RES_XML_RESOURCE_MAP:
            n = (csize - chdr) // 4
            res_ids = list(struct.unpack_from("<%dI" % n, data, off + chdr))
        elif ctype == RES_XML_START_ELEMENT:
            line, comment, ns, name, attr_start, attr_size, attr_count, _, _, _ = struct.unpack_from(
                "<IIIIHHHHHH", data, off + 8)
            attrs = []
            a = off + 16 + attr_start
            for _i in range(attr_count):
                ans, aname, raw, vsize, res0, dtype, dval = struct.unpack_from("<IIIHBBI", data, a)
                a += attr_size
                an = strings[aname] if aname < len(strings) else "?"
                if raw != 0xFFFFFFFF and raw < len(strings):
                    val = strings[raw]
                elif dtype == 0x03 and dval < len(strings):
                    val = strings[dval]
                elif dtype == 0x12:
                    val = "true" if dval else "false"
                elif dtype == 0x01:
                    rid = res_ids[dval] if dval < len(res_ids) else 0
                    val = "@0x%08x" % rid
                elif dtype == 0x10:
                    val = str(struct.unpack("<i", struct.pack("<I", dval))[0])
                else:
                    val = "0x%08x" % dval
                attrs.append((an, val))
            line_out = "  " * depth + "<" + (strings[name] if name < len(strings) else "?")
            for an, val in attrs:
                line_out += ' %s="%s"' % (an, val.replace('"', "&quot;"))
            out.append(line_out + ">")
            depth += 1
        elif ctype == RES_XML_END_ELEMENT:
            depth -= 1
            line, comment, ns, name = struct.unpack_from("<IIII", data, off + 8)
            out.append("  " * depth + "</" + (strings[name] if name < len(strings) else "?") + ">")
        off += csize
    return "\n".join(out)

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(decode(open(sys.argv[1], "rb").read()))