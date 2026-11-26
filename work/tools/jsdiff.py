"""Character-level diff of two mostly-minified JS harness files.

    python work/tools/jsdiff.py old.js new.js [--report out.md] [--max 120]

Line diff first (cheap, files are ~1.4k lines), then a character diff inside
every changed line pair, so a 7 KB change inside a 40 KB template literal shows
up as a few precise deltas instead of one giant hunk.
"""
import difflib
import os
import sys

CTX = 90
SIDE = 400


def char_regions(a, b):
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return [op for op in sm.get_opcodes() if op[0] != 'equal']


def show(s):
    s = s.replace('\r', '')
    if len(s) > SIDE:
        return s[:SIDE] + '  [...%d more chars]' % (len(s) - SIDE)
    return s


def main(a_path, b_path, report, maxreg):
    a = open(a_path, encoding='utf-8', errors='replace').read()
    b = open(b_path, encoding='utf-8', errors='replace').read()
    al, bl = a.splitlines(), b.splitlines()
    out = ['# JS diff  %s -> %s' % (os.path.basename(a_path), os.path.basename(b_path)), '',
           'chars %d -> %d   lines %d -> %d' % (len(a), len(b), len(al), len(bl)), '']
    sm = difflib.SequenceMatcher(None, al, bl, autojunk=False)
    nreg = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        nreg += 1
        out.append('## region %d  %s  old lines %d..%d  new lines %d..%d  (-%d +%d lines)'
                   % (nreg, tag, i1 + 1, i2, j1 + 1, j2, i2 - i1, j2 - j1))
        out.append('')
        old = al[i1:i2]
        new = bl[j1:j2]
        pairs = max(len(old), len(new))
        for k in range(pairs):
            oa = old[k] if k < len(old) else ''
            nb = new[k] if k < len(new) else ''
            if oa == nb:
                continue
            if not oa:
                out.append('   + whole line %d (%d chars): %s' % (j1 + k + 1, len(nb), show(nb)))
                out.append('')
                continue
            if not nb:
                out.append('   - whole line %d (%d chars): %s' % (i1 + k + 1, len(oa), show(oa)))
                out.append('')
                continue
            cr = char_regions(oa, nb)
            out.append('   line old %d / new %d: %d char deltas' % (i1 + k + 1, j1 + k + 1, len(cr)))
            for op, s1, e1, s2, e2 in cr:
                pre = oa[max(0, s1 - CTX):s1].replace('\n', '\\n')
                out.append('     ..%s' % pre)
                out.append('     - %s' % show(oa[s1:e1].replace('\n', '\\n')))
                out.append('     + %s' % show(nb[s2:e2].replace('\n', '\\n')))
            out.append('')
        if nreg >= maxreg:
            out.append('(stopped at %d regions)' % maxreg)
            break
    txt = '\n'.join(out) + '\n'
    if report:
        os.makedirs(os.path.dirname(report) or '.', exist_ok=True)
        open(report, 'w', encoding='utf-8').write(txt)
    print(txt[:24000])
    print('[report] %s (%d lines, %d regions)' % (report, txt.count('\n'), nreg))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    argv = sys.argv[1:]
    rep = 'work/analysis/js_diff.md'
    mx = 120
    if '--report' in argv:
        rep = argv[argv.index('--report') + 1]
    if '--max' in argv:
        mx = int(argv[argv.index('--max') + 1])
    paths = [a for a in argv if not a.startswith('--') and a not in (rep, str(mx))]
    main(paths[0], paths[1], rep, mx)
