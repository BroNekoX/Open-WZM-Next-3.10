"""Build the harness JS: one stage, one output.

    python work/lab_patch.py           # work/cn/lab_startup_v22.js
    python work/lab_patch.py --check   # syntax only

Base is work/cn/lab_startup_v21.js (the last shipped build). patch_v22.py ports
the useful upstream changes on top of it; every edit is anchored and asserted.
"""
import hashlib
import os
import subprocess
import sys

BASE = 'work/cn/lab_startup_v21.js'
STAGE = 'work/patch_v22.py'
FINAL = 'work/cn/lab_startup_v22.js'


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(' '.join(cmd) + '\n' + (r.stdout + r.stderr)[-2000:])


def main():
    if '--check' in sys.argv:
        run(['node', '--check', FINAL])
        print(FINAL + ': syntax ok')
        return
    for p in (BASE, STAGE):
        if not os.path.exists(p):
            sys.exit('missing ' + p)
    run([sys.executable, STAGE])
    run(['node', '--check', FINAL])
    data = open(FINAL, 'rb').read()
    print('\n%s: %s bytes  sha256=%s' % (FINAL, format(len(data), ','), hashlib.sha256(data).hexdigest()[:16]))
    print('next: python work/build.py ' + FINAL + ' work/out/v24.apks')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
