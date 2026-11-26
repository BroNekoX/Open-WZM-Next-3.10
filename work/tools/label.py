"""Rewrite the launcher label inside a split APK.

    python work/label.py work/cn/base.apk.orig "WZM3.10 Next" work/cn/resources_v31.arsc

The label lives as a plain string in the global string pool of resources.arsc
(aapt2 calls it application-label). Rewriting it means rebuilding that pool:
string lengths change, so every offset, the pool size and the table header size
have to be recomputed. Styles (if any) are copied verbatim and stay valid because
their offsets are relative to styles_start.

Everything else in the table is untouched: the string order is preserved, so
resource entries that point at an index keep working.

  --self-test   also build work/tmp/label_test.apk and print what aapt2 sees
"""
import os
import shutil
import struct
import subprocess
import sys
import zipfile

AAPT2 = 'work/tools/android-14/aapt2.exe'
POOL = 0x0001
TABLE = 0x0002
UTF8_FLAG = 0x100


def read_len8(buf, p):
    n = buf[p]
    p += 1
    if n & 0x80:
        n = ((n & 0x7F) << 8) | buf[p]
        p += 1
    return n, p


def read_len16(buf, p):
    n = struct.unpack_from('<H', buf, p)[0]
    p += 2
    if n & 0x8000:
        n = ((n & 0x7FFF) << 16) | struct.unpack_from('<H', buf, p)[0]
        p += 2
    return n, p


def write_len8(n):
    if n > 0x7F:
        return bytes([(n >> 8) | 0x80, n & 0xFF])
    return bytes([n])


def parse_pool(buf, off):
    typ, hsize, size, count, style_count, flags, strings_start, styles_start = \
        struct.unpack_from('<HHIIIIII', buf, off)
    if typ != POOL:
        raise ValueError('no string pool at %d (type %#x)' % (off, typ))
    offsets = list(struct.unpack_from('<%dI' % count, buf, off + hsize)) if count else []
    styles = list(struct.unpack_from('<%dI' % style_count, buf, off + hsize + 4 * count)) if style_count else []
    base = off + strings_start
    strings = []
    for o in offsets:
        p = base + o
        if flags & UTF8_FLAG:
            _, p = read_len8(buf, p)          # length in UTF-16 units
            n, p = read_len8(buf, p)          # length in UTF-8 bytes
            strings.append(buf[p:p + n].decode('utf-8', 'surrogatepass'))
        else:
            n, p = read_len16(buf, p)
            strings.append(buf[p:p + 2 * n].decode('utf-16-le', 'surrogatepass'))
    styles_blob = buf[off + styles_start:off + size] if styles_start else b''
    return dict(hsize=hsize, size=size, count=count, style_count=style_count, flags=flags,
                strings=strings, styles=styles, styles_blob=styles_blob)


def build_pool(pool, strings):
    utf8 = bool(pool['flags'] & UTF8_FLAG)
    blob = bytearray()
    offsets = []
    for s in strings:
        offsets.append(len(blob))
        if utf8:
            raw = s.encode('utf-8', 'surrogatepass')
            units = len(s.encode('utf-16-le', 'surrogatepass')) // 2
            blob += write_len8(units) + write_len8(len(raw)) + raw + b'\x00'
        else:
            raw = s.encode('utf-16-le', 'surrogatepass')
            n = len(raw) // 2
            blob += (struct.pack('<H', n) if n <= 0x7FFF else
                     struct.pack('<HH', (n >> 16) | 0x8000, n & 0xFFFF)) + raw + b'\x00\x00'
    count, style_count = len(strings), pool['style_count']
    hsize = pool['hsize']
    strings_start = hsize + 4 * count + 4 * style_count
    styles_start = strings_start + len(blob) if style_count else 0
    size = strings_start + len(blob) + len(pool['styles_blob'])
    pad = (-size) % 4                      # chunk size must stay 4-byte aligned
    out = bytearray()
    out += struct.pack('<HHIIIIII', POOL, hsize, size, count, style_count, pool['flags'],
                       strings_start, styles_start)
    out += struct.pack('<%dI' % count, *offsets)
    if style_count:
        out += struct.pack('<%dI' % style_count, *pool['styles'])
    out += blob
    out += pool['styles_blob']
    out += b'\x00' * pad
    size += pad
    struct.pack_into('<I', out, 4, size)
    return bytes(out), size


def patch_arsc(arsc, old, new):
    typ, hsize, total = struct.unpack_from('<HHI', arsc, 0)
    if typ != TABLE:
        raise ValueError('not a resources.arsc (type %#x)' % typ)
    pool_off = hsize
    pool = parse_pool(arsc, pool_off)
    hits = [i for i, s in enumerate(pool['strings']) if s == old]
    if not hits:
        raise SystemExit('label %r not found in the global string pool' % old)
    strings = list(pool['strings'])
    for i in hits:
        strings[i] = new
    chunk, _ = build_pool(pool, strings)
    new_arsc = arsc[:pool_off] + chunk + arsc[pool_off + pool['size']:]
    new_total = len(new_arsc)
    new_arsc = bytearray(new_arsc)
    struct.pack_into('<I', new_arsc, 4, new_total)
    return bytes(new_arsc), hits


def self_test(apk, arsc_path, label):
    tmp = 'work/tmp/label_test.apk'
    if os.path.exists(tmp):
        os.remove(tmp)
    with zipfile.ZipFile(apk) as zin, zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = open(arsc_path, 'rb').read() if info.filename == 'resources.arsc' else zin.read(info)
            zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            zi.compress_type = info.compress_type
            zi.external_attr = info.external_attr
            zout.writestr(zi, data)
    r = subprocess.run([AAPT2, 'dump', 'badging', tmp], capture_output=True, text=True)
    if r.returncode != 0:
        print('aapt2 failed:\n' + (r.stdout + r.stderr)[-800:])
        return False
    for line in r.stdout.splitlines():
        if line.startswith('application-label') or line.startswith('application:') or \
                line.startswith('launchable-activity'):
            print('  ' + line)
    return ('application-label:%r' % label) in r.stdout


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    if len(args) < 3:
        sys.exit(__doc__)
    apk, label, out_arsc = args[0], args[1], args[2]
    with zipfile.ZipFile(apk) as z:
        arsc = z.read('resources.arsc')
    pool = parse_pool(arsc, struct.unpack_from('<H', arsc, 2)[0])
    index = [i for i, s in enumerate(pool['strings']) if s.startswith('WZM')]
    print('pool: %d strings, flags=%#x, WZM-like: %s' % (len(pool['strings']), pool['flags'],
          [(i, pool['strings'][i]) for i in index[:6]]))
    old = pool['strings'][index[0]] if index else None
    if old is None:
        sys.exit('no WZM* string in the pool')
    new_arsc, hits = patch_arsc(arsc, old, label)
    os.makedirs(os.path.dirname(out_arsc) or '.', exist_ok=True)
    open(out_arsc, 'wb').write(new_arsc)
    print('%r -> %r at indexes %s ; arsc %d -> %d bytes -> %s'
          % (old, label, hits, len(arsc), len(new_arsc), out_arsc))
    if '--self-test' in argv:
        ok = self_test(apk, out_arsc, label)
        print('self-test:', 'OK' if ok else 'FAILED')
        return 0 if ok else 1
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main(sys.argv[1:]))
