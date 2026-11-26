"""Minimal ELF64 little-endian parser: sections, segments, dynamic, dynsym."""
import struct

class ELF:
    def __init__(self, path):
        self.path = path
        self.data = open(path, "rb").read()
        d = self.data
        assert d[:4] == b"\x7fELF", "not ELF"
        self.is64 = d[4] == 2
        e = "<" if d[5] == 1 else ">"
        self.endian = e
        (self.e_type, self.e_machine, self.e_version, self.e_entry, self.e_phoff,
         self.e_shoff, self.e_flags, self.e_ehsize, self.e_phentsize, self.e_phnum,
         self.e_shentsize, self.e_shnum, self.e_shstrndx) = struct.unpack_from(e + "HHIQQQIHHHHHH", d, 16)
        self.segments = []
        for i in range(self.e_phnum):
            o = self.e_phoff + i * self.e_phentsize
            p_type, p_flags, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_align = struct.unpack_from(
                e + "IIQQQQQQ", d, o)
            self.segments.append(dict(type=p_type, flags=p_flags, offset=p_offset, vaddr=p_vaddr,
                                      filesz=p_filesz, memsz=p_memsz, align=p_align))
        self.sections = []
        for i in range(self.e_shnum):
            o = self.e_shoff + i * self.e_shentsize
            sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size, sh_link, sh_info, sh_align, sh_entsize = \
                struct.unpack_from(e + "IIQQQQIIQQ", d, o)
            self.sections.append(dict(name_off=sh_name, type=sh_type, flags=sh_flags, addr=sh_addr,
                                      offset=sh_offset, size=sh_size, link=sh_link, info=sh_info,
                                      align=sh_align, entsize=sh_entsize))
        if self.sections and self.e_shstrndx < len(self.sections):
            strtab = self.sections[self.e_shstrndx]
            base = strtab["offset"]
            for s in self.sections:
                end = d.index(b"\0", base + s["name_off"])
                s["name"] = d[base + s["name_off"]:end].decode("latin1")
        self.dynamic = {}
        self.needed = []

    def section(self, name):
        for s in self.sections:
            if s.get("name") == name:
                return s
        return None

    def vaddr_to_offset(self, addr):
        for p in self.segments:
            if p["type"] == 1 and p["vaddr"] <= addr < p["vaddr"] + p["filesz"]:
                return p["offset"] + (addr - p["vaddr"])
        return None

    def parse_dynamic(self):
        dyn = self.section(".dynamic")
        if not dyn:
            return
        e = self.endian
        # DT_STRTAB addr -> find offset
        entries = []
        for o in range(dyn["offset"], dyn["offset"] + dyn["size"], 16):
            tag, val = struct.unpack_from(e + "qQ", self.data, o)
            entries.append((tag, val))
            if tag == 0:
                break
        strtab_addr = dict(entries).get(5)
        strtab = None
        if strtab_addr is not None:
            off = self.vaddr_to_offset(strtab_addr)
            sec = self.section(".dynstr")
            if off is not None:
                size = sec["size"] if sec else 0x10000
                strtab = self.data[off:off + size]
        self.dynamic = dict(entries)
        for tag, val in entries:
            if tag == 1 and strtab is not None:
                end = strtab.index(b"\0", val)
                self.needed.append(strtab[val:end].decode("latin1"))
        if 14 in dict(entries) and strtab is not None:  # DT_SONAME
            v = dict(entries)[14]
            end = strtab.index(b"\0", v)
            self.soname = strtab[v:end].decode("latin1")
        else:
            self.soname = None

    def dynamic_symbols(self):
        """Return list of dicts for .dynsym using DT_SYMTAB/DT_STRTAB."""
        e = self.endian
        dyn = self.dynamic
        if not dyn or 6 not in dyn:
            return []
        symtab_addr = dyn[6]
        strtab_addr = dyn[5]
        hash_addr = dyn.get(4)
        gnu_hash_addr = dyn.get(0x6ffffef5)
        n = 0
        if hash_addr:
            off = self.vaddr_to_offset(hash_addr)
            n = struct.unpack_from(e + "II", self.data, off)[1]
        elif gnu_hash_addr:
            off = self.vaddr_to_offset(gnu_hash_addr)
            nbuckets, symoffset, bloom_size, bloom_shift = struct.unpack_from(e + "IIII", self.data, off)
            buckets_off = off + 16 + bloom_size * 8
            maxb = 0
            for i in range(nbuckets):
                b = struct.unpack_from(e + "I", self.data, buckets_off + 4 * i)[0]
                maxb = max(maxb, b)
            # walk chain from last bucket
            if maxb:
                chain_off = buckets_off + 4 * nbuckets
                i = maxb
                while True:
                    h = struct.unpack_from(e + "I", self.data, chain_off + 4 * (i - symoffset))[0]
                    n = i + 1
                    if h & 1:
                        break
                    i += 1
        if not n:
            # fallback: use .dynsym section size
            s = self.section(".dynsym")
            if s:
                n = s["size"] // 24
        sym_off = self.vaddr_to_offset(symtab_addr)
        str_off = self.vaddr_to_offset(strtab_addr)
        out = []
        for i in range(n):
            name, info, other, shndx, value, size = struct.unpack_from(e + "IBBHQQ", self.data, sym_off + 24 * i)
            end = self.data.index(b"\0", str_off + name)
            out.append(dict(name=self.data[str_off + name:end].decode("latin1"), info=info,
                            shndx=shndx, value=value, size=size))
        return out


if __name__ == "__main__":
    import sys
    e = ELF(sys.argv[1])
    e.parse_dynamic()
    print("soname:", e.soname)
    print("needed:", e.needed)
    print("sections:")
    for s in e.sections:
        print(f"  {s['name']:<18} addr=0x{s['addr']:08x} off=0x{s['offset']:08x} size=0x{s['size']:x} type={s['type']}")
    syms = e.dynamic_symbols()
    print("dynsyms:", len(syms))