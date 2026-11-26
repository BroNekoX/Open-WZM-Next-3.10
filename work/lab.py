"""Single device CLI for the lab build.

    python work/lab.py status              one status snapshot via the property channel
    python work/lab.py log [lines]         tail of the in-app log ring
    python work/lab.py send <file.js> [s]  run a JS snippet in the harness
    python work/lab.py lua <file.lua> [s]  run a Lua snippet in the game state
    python work/lab.py code "<js>"         inline JS
    python work/lab.py texture 0|1|2       switch texture quality (0 = native, 1 = mid, 2 = low)
    python work/lab.py config <file.json>  write the harness config.json
    python work/lab.py install [x.apks]    install/upgrade in place and keep the data
    python work/lab.py launch | stop | wake
    python work/lab.py gpu [n]             GPU busy samples (the only usable fps proxy)

Transport (never on the boot path):
    adb push cmd.json  -> /sdcard/Android/media/<pkg>/cmd.json
    adb shell setprop debug.wzm.cmd <id>     the only trigger the app sees
    the app writes out.json once, from its own timer thread
"""
import os
import shutil
import subprocess
import sys
import time
import json
import zipfile
import zlib

ADB = 'work/tools/platform-tools/adb.exe'
SERIAL = '6058fbe3'
PKG = 'com.activision.callofduty.wzm310x'
MEDIA = '/sdcard/Android/media/' + PKG + '/'
_seq = 0
TMP = os.path.abspath('work/tmp')
ENV = dict(os.environ, TEMP=TMP, TMP=os.environ.get('TEMP', TMP), TMPDIR=TMP)
DEFAULT_APKS = 'WZM3.10-Next-CN-v3.1.apks'


def adb(*args, capture=True, timeout=600):
    return subprocess.run([ADB, '-s', serial()] + list(args), capture_output=capture,
                          encoding='utf-8', errors='replace', env=ENV, timeout=timeout)


def serial():
    global SERIAL
    if SERIAL:
        return SERIAL
    out = subprocess.run([ADB, 'devices'], capture_output=True, text=True, env=ENV).stdout
    for line in out.splitlines()[1:]:
        if '\tdevice' in line:
            SERIAL = line.split('\t')[0].strip()
            return SERIAL
    sys.exit('no device: plug the phone in and allow USB debugging')


def shell(cmd):
    return adb('shell', cmd).stdout or ''


def push(local, remote):
    r = adb('push', os.path.abspath(local), remote)
    if r.returncode != 0:
        sys.exit('push failed: ' + (r.stdout or '') + (r.stderr or ''))


def cmd(payload, wait=75.0):
    """Push one command, fire the property trigger, wait for out.json."""
    os.makedirs(TMP, exist_ok=True)
    local = os.path.join(TMP, 'cmd.json')
    open(local, 'w', encoding='utf-8', newline='\n').write(json.dumps(payload, ensure_ascii=False))
    # drop the previous answer first, otherwise a stale file with a recycled id
    # can be parsed as this command's result
    shell('rm -f ' + MEDIA + 'out.json')
    push(local, MEDIA + 'cmd.json')
    shell('setprop debug.wzm.cmd ' + payload['id'])
    t0 = time.time()
    while time.time() - t0 < wait:
        time.sleep(1.5)
        raw = shell('cat ' + MEDIA + 'out.json 2>/dev/null').strip()
        if not raw.startswith('{'):
            continue
        try:
            doc = json.loads(raw)
        except ValueError:
            continue
        if doc.get('id') == payload['id']:
            return doc
    return None


def new_id(prefix):
    global _seq
    _seq = (_seq + 1) % 1000
    return '%s%d%03d' % (prefix, int(time.time() * 1000) % 1000000, _seq)


def show(doc, pretty=True):
    if doc is None:
        print('timeout: no out.json (is the game past the menu? is the channel armed after 45 s?)')
        return 1
    if not doc.get('ok'):
        print('ERROR:', doc.get('error'))
        return 1
    r = doc.get('result')
    print(json.dumps(r, ensure_ascii=False, indent=1) if pretty and not isinstance(r, str) else r)
    return 0


def _crc(path):
    c = 0
    with open(path, 'rb') as f:
        while True:
            b = f.read(1 << 22)
            if not b:
                return c & 0xFFFFFFFF
            c = zlib.crc32(b, c)


def install(apks):
    if not os.path.exists(apks):
        sys.exit('missing ' + apks)
    work = os.path.join('work', 'tmp', 'install')
    os.makedirs(work, exist_ok=True)
    paths = []
    with zipfile.ZipFile(apks) as z:
        for n in z.namelist():
            if not n.endswith('.apk'):
                continue
            dst = os.path.join(work, n)
            info = z.getinfo(n)
            # size alone is not enough: two different builds can land on the same
            # byte count (zipalign padding), so compare the CRC before reusing.
            if not (os.path.exists(dst) and os.path.getsize(dst) == info.file_size
                    and _crc(dst) == info.CRC):
                with z.open(n) as s, open(dst, 'wb') as d:
                    shutil.copyfileobj(s, d, 1 << 22)
            paths.append(dst)
    print('installing %d splits (in place)...' % len(paths))
    r = adb('install-multiple', '-r', '--no-streaming', *paths, timeout=1800)
    print((r.stdout or '') + (r.stderr or ''))
    sys.exit(0 if r.returncode == 0 else 1)


def gpu(n=5):
    keys = ('/sys/class/kgsl/kgsl-3d0/gpubusy', '/sys/class/kgsl/kgsl-3d0/devfreq/gpu_load')
    for i in range(n):
        vals = []
        for k in keys:
            v = shell('cat ' + k + ' 2>/dev/null').split()
            try:
                busy, total = int(v[0]), int(v[1])
            except (IndexError, ValueError):
                continue
            if total > 0:
                vals.append('%.0f%%' % (100.0 * busy / total))
                break
        print('gpu %d: %s' % (i + 1, vals[0] if vals else 'n/a'))
        time.sleep(1.0)


def main():
    a = sys.argv[1:]
    if not a or a[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    op = a[0]
    if op == 'status':
        return show(cmd({'id': new_id('s'), 'op': 'status'}, 60))
    if op == 'log':
        return show(cmd({'id': new_id('g'), 'op': 'log', 'lines': int(a[1]) if len(a) > 1 else 8000}, 60), False)
    if op == 'send':
        return show(cmd({'id': new_id('c'), 'code': open(a[1], encoding='utf-8').read()},
                        float(a[2]) if len(a) > 2 else 45.0))
    if op == 'lua':
        return show(cmd({'id': new_id('l'), 'lua': open(a[1], encoding='utf-8').read()},
                        float(a[2]) if len(a) > 2 else 45.0), False)
    if op == 'code':
        return show(cmd({'id': new_id('c'), 'code': a[1]}, float(a[2]) if len(a) > 2 else 45.0))
    if op == 'texture':
        return show(cmd({'id': new_id('t'), 'lua': "return 'local-texture-quality:" + a[1] + "'"}, 45), False)
    if op == 'config':
        body = json.dumps(json.load(open(a[1], encoding='utf-8')))
        code = 'return String(labFs.put(dir+\'config.json\',' + json.dumps(body) + '))'
        return show(cmd({'id': new_id('f'), 'code': code}, 45))
    if op == 'install':
        install(a[1] if len(a) > 1 else DEFAULT_APKS)
    if op == 'launch':
        print(shell('am start -n %s/com.activision.game.MainActivity' % PKG))
        return 0
    if op == 'stop':
        print(shell('am force-stop ' + PKG))
        return 0
    if op == 'wake':
        shell('input keyevent KEYCODE_WAKEUP')
        shell('svc power stayon true')
        shell('cmd statusbar collapse')
        print('awake')
        return 0
    if op == 'gpu':
        gpu(int(a[1]) if len(a) > 1 else 5)
        return 0
    sys.exit('unknown op ' + op)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
