"""Revert the v3 streaming-download override on top of the 3.1 harness.

    python work/patch_v31.py [base.js] [out.js]

BASE  default work/new/v31.js            3.1 harness, extracted from its arm split
FINAL default work/cn/lab_startup_v31.js  build input for work/build.py

Why: v3 forced stream_http=0/stream_http_prefetch=0 ("offline streaming") on the
first bridge tick, which starved texture mips (blurry world). 3.1 flipped
stream_http back to 1 but pinned prefetch off with a raw dvar write. Field
symptom after that: HD model downloads crash at random and models render with
incomplete PBR. This patch removes both writes and keeps a read-only snapshot
for out.json, so the engine's own streaming setup is untouched (the state v14
shipped, before the override existed).
"""
import hashlib
import os
import subprocess
import sys

BASE = sys.argv[1] if len(sys.argv) > 1 else 'work/new/v31.js'
FINAL = sys.argv[2] if len(sys.argv) > 2 else 'work/cn/lab_startup_v31.js'

READ_BLOCK = r'''  /* Streaming dvars stay read-only in this build. v3 forced stream_http=0 and
     stream_http_prefetch=0 on the first bridge tick, which starved the texture
     mips (blurry world). 3.1 restored stream_http=1 but still pinned prefetch
     off with a raw dvar write; the remaining faults (HD model download crash,
     incomplete PBR maps) match that pin. Neither dvar is written here any more,
     so the engine keeps the setup it boots with. */
  globalThis.labStreamRead=function(){
   const done={};
   for(const item of [['stream_http',0xc038170],['stream_http_prefetch',0xc0bd628]]){
    try{
     const d=b.add(item[1]).readPointer();
     if(d.isNull()||d.compare(ptr(0x1000))<0){done[item[0]]='null';continue;}
     done[item[0]]=d.add(0x28).readS32();
    }catch(e){done[item[0]]='err';}
   }
   return done;
  };
'''

COUNT = {'config': 0, 'call': 0, 'status': 0, 'block': 0}


def one(text, old, new, key):
    n = text.count(old)
    if n != 1:
        sys.exit('%s: expected 1 occurrence, found %d' % (key, n))
    COUNT[key] += 1
    return text.replace(old, new, 1)


def drop_function(lines, name):
    """Delete the 'name=function(){' block through its matching '  };' line."""
    start = None
    for i, ln in enumerate(lines):
        if ln.strip().startswith(name + '=function(){'):
            start = i
            break
    if start is None:
        sys.exit('block %s not found' % name)
    end = None
    for j in range(start + 1, len(lines)):
        if lines[j].strip() == '};':
            end = j
            break
    if end is None:
        sys.exit('block %s has no end' % name)
    body = ''.join(lines[start:end + 1])
    for need in ('stream_http', 'stream_http_prefetch', 'setInt'):
        if need not in body:
            sys.exit('block %s does not look like the streaming override' % name)
    return lines[:start] + [READ_BLOCK + '\n'] + lines[end + 1:]


def main():
    src = open(BASE, encoding='utf-8').read()
    if 'globalThis.labStreamRead=' in src:
        sys.exit('already patched? ' + BASE + ' contains labStreamRead')
    src = one(src, 'stream:true,prefetch:false,', '', 'config')
    lines = src.splitlines(keepends=True)
    for i, ln in enumerate(lines):
        if 'globalThis.labStreamOff' in ln:
            if 'labApplyStreaming' not in ln:
                sys.exit('labStreamOff line does not match the 3.1 shape')
            del lines[i]
            COUNT['call'] += 1
            break
    else:
        sys.exit('labStreamOff call site not found')
    lines = drop_function(lines, 'globalThis.labApplyStreaming')
    COUNT['block'] += 1
    src = ''.join(lines)
    src = one(src, 'out.stream=globalThis.labStreamState||null;',
              'out.stream=globalThis.labStreamRead?globalThis.labStreamRead():null;', 'status')
    for bad in ('labApplyStreaming', 'labStreamOff', 'labStreamState'):
        if bad in src:
            sys.exit('leftover reference: ' + bad)
    if 'LAB_CFG.stream' in src or 'LAB_CFG.prefetch' in src:
        sys.exit('leftover LAB_CFG streaming key')
    os.makedirs(os.path.dirname(FINAL), exist_ok=True)
    open(FINAL, 'w', encoding='utf-8', newline='\n').write(src)
    r = subprocess.run(['node', '--check', FINAL], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit('node --check failed\n' + (r.stdout + r.stderr)[-2000:])
    data = open(FINAL, 'rb').read()
    print('edits: ' + ' '.join('%s=%d' % kv for kv in COUNT.items()))
    print('%s: %s bytes  sha256=%s' % (FINAL, format(len(data), ','), hashlib.sha256(data).hexdigest()[:16]))
    print('next: WZM_ARM=work/new/a31/arm.apk python work/build.py %s WZM3.10-Next-CN-v3.1.apks' % FINAL)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
