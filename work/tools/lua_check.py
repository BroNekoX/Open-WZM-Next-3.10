"""Offline Lua sanity check: strip comments/strings, verify block balance,
and (strict mode) reject a chunk-level 'return'.

The lab prelude is glued in front of the stock bootstrap chunk, so a chunk-level
return there would skip the code that builds the menu. Returns are only legal
inside a function.
"""
import sys

OPENERS = {'function', 'if', 'repeat', 'do'}
CLOSERS = {'end', 'until'}


def tokens(src):
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        if c == '-' and src.startswith('--', i):
            j = src.find(chr(10), i)
            i = n if j < 0 else j + 1
            continue
        if c in '"\'':
            q = c
            i += 1
            while i < n:
                if src[i] == '\\':
                    i += 2
                    continue
                if src[i] == q:
                    i += 1
                    break
                i += 1
            continue
        if c == '[' and src.startswith('[[', i):
            j = src.find(']]', i)
            i = n if j < 0 else j + 2
            continue
        if c.isalpha() or c == '_':
            j = i
            while j < n and (src[j].isalnum() or src[j] == '_'):
                j += 1
            yield src[i:j]
            i = j
            continue
        if c == '(':
            yield '('
        elif c == ')':
            yield ')'
        i += 1


def check(path, forbid_chunk_return=False):
    src = open(path, encoding='utf-8').read()
    stack = []
    paren = 0
    prev = ''
    worst = 0
    stray = 0
    bad_returns = []
    line = 1
    for tok in tokens(src):
        if tok in ('for', 'while'):
            prev = tok
            continue
        if tok == 'do':
            if prev in ('for', 'while'):
                prev = 'do'
                continue
            stack.append('do')
        elif tok in ('function', 'if', 'repeat'):
            stack.append(tok)
        elif tok == 'end':
            if stack:
                stack.pop()
            else:
                stray += 1   # an 'end' with nothing open: the chunk will not compile
        elif tok == 'until':
            if stack and stack[-1] == 'repeat':
                stack.pop()
        elif tok == '(':
            paren += 1
        elif tok == ')':
            paren -= 1
        elif tok == 'return' and forbid_chunk_return and 'function' not in stack:
            bad_returns.append(len(stack))
        worst = min(worst, len(stack))
        prev = tok
    ok = not stack and paren == 0 and not bad_returns and stray == 0 and worst >= 0
    print('%s: blocks=%d parens=%d min_depth=%d stray_end=%d chunk_return=%d -> %s'
          % (path, len(stack), paren, worst, stray, len(bad_returns), 'OK' if ok else 'BROKEN'))
    return 0 if ok else 1


if __name__ == '__main__':
    args = sys.argv[1:]
    strict = '--strict' in args
    files = [a for a in args if not a.startswith('--')]
    sys.exit(max(check(f, strict) for f in files) if files else 1)
