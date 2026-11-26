"""Compare two split APKs entry by entry, tolerant of renamed splits.

    python work/tools/splitdiff.py --list  a.apk
    python work/tools/splitdiff.py a.apk b.apk --report work/analysis/split_diff.md [--lines 400]

Entries are matched by basename, so base.apk inside one bundle and
base.apk inside another (or arm.apk vs split_config.arm64_v8a.apk) line up.
Text entries (the harness JS) get a unified diff; binaries get size/sha/first
differing byte. Summary table always goes to stdout.
"""
import difflib
import hashlib
import os
import sys
import zipfile

TEXT_MAX = 8 << 20


def sha(b):
    return hashlib.sha256(b).hexdigest()


def is_text(b):
    if b'\x00' in b[:8192]:
        return False
    try:
        b[:8192].decode('utf-8')
        return True
    except UnicodeDecodeError:
        return False


def index(z):
    out = {}
    for i in z.infolist():
        base = i.filename.rsplit('/', 1)[-1]
        out[base] = i.filename
    return out


def first_diff(a, b):
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    return -1 if len(a) == len(b) else n


def diff_text(a, b, name, lines):
    al = a.decode('utf-8', 'replace').splitlines()
    bl = b.decode('utf-8', 'replace').splitlines()
    d = list(difflib.unified_diff(al, bl, 'v3/' + name, 'v3.1/' + name, lineterm='', n=3))
    add = sum(1 for l in d if l.startswith('+') and not l.startswith('+++'))
    rem = sum(1 for l in d if l.startswith('-') and not l.startswith('---'))
    out = ['### ' + name + '   +%d -%d  (%d B -> %d B)' % (add, rem, len(a), len(b)), '']
    for line in d[:lines]:
        out.append(line)
    if len(d) > lines:
        out.append('... %d more diff lines (rerun with --lines)' % (len(d) - lines))
    out.append('')
    return out, add + rem


def main(argv):
    paths = [a for a in argv if not a.startswith('--')]
    opt = {}
    i = 0
    while i < len(argv):
        a = argv[i]
        if a.startswith('--') and a != '--list':
            opt[a] = argv[i + 1]
            i += 2
            continue
        i += 1
    lines = int(opt.get('--lines', 400))
    if '--list' in argv:
        with zipfile.ZipFile(paths[0]) as z:
            for info in sorted(z.infolist(), key=lambda x: x.filename):
                print('%-56s %12s' % (info.filename, format(info.file_size, ',')))
        return
    a_path, b_path = paths[0], paths[1]
    za, zb = zipfile.ZipFile(a_path), zipfile.ZipFile(b_path)
    ia, ib = index(za), index(zb)
    out = ['# split diff', '', 'A: %s (%s B)' % (os.path.basename(a_path), format(os.path.getsize(a_path), ',')),
           'B: %s (%s B)' % (os.path.basename(b_path), format(os.path.getsize(b_path), ',')), '']
    out.append('| entry | A | B | state |')
    out.append('|---|---|---|---|')
    for name in sorted(set(ia) | set(ib)):
        ea, eb = ia.get(name), ib.get(name)
        if ea is None:
            state = 'only B (' + eb + ')'
            sa = nb = '-'
        elif eb is None:
            state = 'only A (' + ea + ')'
            sa = nb = '-'
        else:
            sa = format(za.getinfo(ea).file_size, ',')
            nb = format(zb.getinfo(eb).file_size, ',')
            crc_a = za.getinfo(ea).CRC
            crc_b = zb.getinfo(eb).CRC
            state = 'same' if crc_a == crc_b else 'DIFF'
        out.append('| ' + name + ' | ' + sa + ' | ' + nb + ' | ' + state + ' |')
    out.append('')
    total = 0
    for name in sorted(set(ia) & set(ib)):
        ea, eb = ia[name], ib[name]
        if za.getinfo(ea).CRC == zb.getinfo(eb).CRC:
            continue
        a = za.read(ea)
        b = zb.read(eb)
        out.append('## ' + name + '  (%d B -> %d B, sha %s.. -> %s..)' % (len(a), len(b), sha(a)[:16], sha(b)[:16]))
        out.append('')
        if max(len(a), len(b)) <= TEXT_MAX and is_text(a) and is_text(b):
            part, n = diff_text(a, b, name, lines)
            out += part
            total += n
        else:
            fd = first_diff(a, b)
            out.append('binary; first differing byte %s; sizes %d / %d' % (fd, len(a), len(b)))
            out.append('')
    out.append('text diff lines: %d' % total)
    txt = '\n'.join(out) + '\n'
    rep = opt.get('--report')
    if rep:
        os.makedirs(os.path.dirname(rep) or '.', exist_ok=True)
        open(rep, 'w', encoding='utf-8').write(txt)
    print('\n'.join(out[:200]))
    print('[report] %s (%d lines)' % (rep, txt.count(chr(10))))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main(sys.argv[1:])
