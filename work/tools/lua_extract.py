"""Pull the embedded Lua chunks out of a harness JS and syntax-check them.

    python work/tools/lua_extract.py work/cn/lab_startup_v31.js

Writes work/tmp/lua_<const>.lua for every "const NAME=<string literal>," it finds
and prints the byte counts. Pair with: python work/tools/lua_check.py <files>
"""
import json
import os
import re
import sys

OUT = 'work/tmp'

ESC = {'n': '\n', 't': '\t', 'r': '\r', '"': '"', "'": "'", '\\': '\\', '/': '/'}


def unescape(body):
    try:
        return json.loads('"' + body + '"')
    except Exception:
        pass
    out, i = [], 0
    while i < len(body):
        c = body[i]
        if c != '\\':
            out.append(c)
            i += 1
            continue
        n = body[i + 1] if i + 1 < len(body) else ''
        if n == 'u' and len(body) >= i + 6:
            try:
                out.append(chr(int(body[i + 2:i + 6], 16)))
            except ValueError:
                out.append('\\u')
            i += 6
            continue
        out.append(ESC.get(n, '\\' + n))
        i += 2
    return ''.join(out)


def grab(text, start):
    """Scan a JS double-quoted literal starting at start (index of the quote)."""
    i, body = start + 1, []
    while i < len(text):
        c = text[i]
        if c == '\\':
            body.append(c)
            body.append(text[i + 1])
            i += 2
            continue
        if c == '"':
            return ''.join(body), i + 1
        body.append(c)
        i += 1
    raise ValueError('unterminated literal')


def main(path):
    text = open(path, encoding='utf-8').read()
    os.makedirs(OUT, exist_ok=True)
    tag = os.path.basename(path).split('.')[0]
    found = 0
    for m in re.finditer(r'const (defaultLua|DSHA_LUA|CLEANUP_LUA)\s*=\s*', text):
        name = m.group(1)
        start = m.end()
        if start >= len(text) or text[start] != '"':
            print('%-12s not a plain literal, skipped' % name)
            continue
        body, _ = grab(text, start)
        lua = unescape(body)
        dst = os.path.join(OUT, 'lua_%s_%s.lua' % (tag.replace('lab_startup_', ''), name.lower()))
        open(dst, 'w', encoding='utf-8', newline='\n').write(lua)
        print('%-12s %7d chars -> %s' % (name, len(lua), dst))
        found += 1
    if not found:
        sys.exit('no embedded Lua found in ' + path)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main(sys.argv[1])
