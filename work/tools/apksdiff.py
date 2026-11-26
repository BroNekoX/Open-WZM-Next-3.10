"""Diff two .apks bundles: outer entries, then entries inside each nested .apk.

    python work/tools/apksdiff.py WZM3.10-Next-CN-v3.apks new/WZM-Next-CN-v3.1.apks

Writes work/analysis/apks_diff.md and prints the same text. Text entries that
differ get a unified diff (truncated); binary entries only get hashes.
"""
import difflib
import hashlib
import io
import os
import sys
import zipfile

LIMIT = 260
TEXT_MAX = 6 << 20


def summ(z):
    out = {}
    for i in z.infolist():
        out[i.filename] = (i.file_size, i.CRC)
    return out


def sha(b):
    return hashlib.sha256(b).hexdigest()[:16]


def looks_text(b):
    if not b:
        return True
    if b.find(b'\x00', 0, 4096) >= 0:
        return False
    try:
        b[:4096].decode('utf-8')
        return True
    except UnicodeDecodeError:
        return False


def text_diff(name, a, b, out):
    al = a.decode('utf-8', 'replace').splitlines()
    bl = b.decode('utf-8', 'replace').splitlines()
    d = list(difflib.unified_diff(al, bl, 'v3/' + name, 'v3.1/' + name, lineterm='', n=2))
    if not d:
        out.append('   (bytes differ, lines identical - line endings)')
        return 0
    add = sum(1 for l in d if l.startswith('+') and not l.startswith('+++'))
    rem = sum(1 for l in d if l.startswith('-') and not l.startswith('---'))
    out.append('   +%d -%d  (%d hunks-ish lines)' % (add, rem, len(d)))
    out.append('')
    for line in d[:LIMIT]:
        out.append('   ' + line[:400])
    if len(d) > LIMIT:
        out.append('   ... %d more diff lines' % (len(d) - LIMIT))
    out.append('')
    return add + rem


def nested(label, abytes, bbytes, out):
    za = zipfile.ZipFile(io.BytesIO(abytes))
    zb = zipfile.ZipFile(io.BytesIO(bbytes))
    ma, mb = summ(za), summ(zb)
    only_a = sorted(set(ma) - set(mb))
    only_b = sorted(set(mb) - set(ma))
    out.append('### ' + label + '  entries: %d -> %d' % (len(ma), len(mb)))
    for n in only_a:
        out.append('   - only in v3: %s (%d B)' % (n, ma[n][0]))
    for n in only_b:
        out.append('   + only in v3.1: %s (%d B)' % (n, mb[n][0]))
    out.append('')
    out.append('| entry | v3 | v3.1 | state |')
    out.append('|---|---|---|---|')
    changed = []
    for n in sorted(set(ma) & set(mb)):
        sa, sb = ma[n][0], mb[n][0]
        if ma[n][1] == mb[n][1]:
            state = 'same'
        else:
            state = 'DIFF'
            changed.append(n)
        out.append('| ' + n + ' | %d | %d | %s |' % (sa, sb, state))
    out.append('')
    total = 0
    for n in changed:
        a = za.read(n)
        b = zb.read(n)
        out.append('#### ' + label + ' :: ' + n + '  (%d -> %d B, sha %s -> %s)' % (len(a), len(b), sha(a), sha(b)))
        if max(len(a), len(b)) <= TEXT_MAX and looks_text(a) and looks_text(b):
            total += text_diff(n, a, b, out)
        else:
            out.append('   binary; first diff at byte %s' % _first_diff(a, b))
            out.append('')
    return total


def _first_diff(a, b):
    for i in range(min(len(a), len(b))):
        if a[i] != b[i]:
            return str(i)
    return 'tail only (%d vs %d)' % (len(a), len(b))


def main(a_path, b_path, report):
    za = zipfile.ZipFile(a_path)
    zb = zipfile.ZipFile(b_path)
    ma, mb = summ(za), summ(zb)
    out = ['# APKS diff', '', 'A: ' + os.path.basename(a_path) + '  %d B' % os.path.getsize(a_path),
           'B: ' + os.path.basename(b_path) + '  %d B' % os.path.getsize(b_path), '']
    out.append('## outer entries')
    out.append('')
    out.append('| entry | A | B | state |')
    out.append('|---|---|---|---|')
    for n in sorted(set(ma) | set(mb)):
        sa = ma.get(n)
        sb = mb.get(n)
        if sa is None:
            st = 'only B'
        elif sb is None:
            st = 'only A'
        elif sa[1] == sb[1]:
            st = 'same'
        else:
            st = 'DIFF'
        out.append('| ' + n + ' | ' + (str(sa[0]) if sa else '-') + ' | ' + (str(sb[0]) if sb else '-') + ' | ' + st + ' |')
    out.append('')
    grand = 0
    for n in sorted(set(ma) & set(mb)):
        if ma[n][1] == mb[n][1]:
            continue
        if not n.lower().endswith('.apk'):
            out.append('## ' + n + ': byte-level difference only')
            out.append('')
            continue
        out.append('## nested: ' + n + '  (%d -> %d B)' % (ma[n][0], mb[n][0]))
        out.append('')
        try:
            grand += nested(n, za.read(n), zb.read(n), out)
        except Exception as exc:
            out.append('   !! nested diff failed: %r' % (exc,))
        out.append('')
    out.append('changed text lines total: %d' % grand)
    txt = '\n'.join(out) + '\n'
    os.makedirs(os.path.dirname(report), exist_ok=True)
    open(report, 'w', encoding='utf-8').write(txt)
    print(txt)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else 'work/analysis/apks_diff.md')
