"""Build one installable APKS from the harness JS and the startup page.

    python work/build.py work/cn/lab_startup_v22.js work/out/v24.apks

Only two splits ever change: arm.apk (harness JS) and base.apk (startup page).
en / xxhdpi / asset are reused from the previous release, byte for byte, so an
in-place upgrade keeps working and the build takes ~3 minutes.
"""
import os
import shutil
import subprocess
import sys
import time
import zipfile

BT = os.environ.get('WZM_BUILD_TOOLS') or 'work/tools/android-14'
JAVA = r'C:\Program Files\Java\jdk-21\bin\java.exe'
if not os.path.exists(JAVA):
    JAVA = shutil.which('java') or 'java'   # fall back to PATH when the JDK moves
APKSIGNER = os.path.join(BT, 'lib', 'apksigner.jar')
ZIPALIGN = os.path.join(BT, 'zipalign.exe')
# Your own signing key. No key material is shipped with this repo.
KS = os.environ.get('WZM_KS') or 'release/wzm.keystore'
KS_PASS = os.environ.get('WZM_KS_PASS') or ''
ALIAS = os.environ.get('WZM_KS_ALIAS') or 'wzm'
OUT = 'work/out'
SPLITS = os.path.join(OUT, 'splits')
SOURCE_APKS = 'WZM3.10-Lab-CN-v14.apks'
SOURCE_FALLBACK = ['work/out/v24.apks', 'work/out/v23.apks']   # any package that still carries asset/en/xx
FIXED = ['en.apk', 'xx.apk', 'asset.apk']

# arm split to repack: override with WZM_ARM when the base comes from another build
ARM_SRC = os.environ.get('WZM_ARM') or 'work/cn/arm.apk'
ARM_ENTRY = 'lib/arm64-v8a/liblab.startup.so'
BASE_SRC = 'work/cn/base.apk.orig'
BASE_REPLACE = {
    'assets/bootstrap/index.html': os.environ.get('WZM_PAGE') or 'assets/index_v31.html',
}


def run(args):
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(' '.join(map(str, args))[:200] + '\n' + (r.stdout + r.stderr)[-1500:])


def ensure_splits():
    os.makedirs(SPLITS, exist_ok=True)
    missing = [n for n in FIXED if not os.path.exists(os.path.join(SPLITS, n))]
    if not missing:
        print('   reusing cached splits: ' + ', '.join(FIXED))
        return
    source = SOURCE_APKS
    if not os.path.exists(source):
        source = next((p for p in SOURCE_FALLBACK if os.path.exists(p)), None)
    if source is None:
        sys.exit('missing splits and no source package: restore ' + SOURCE_APKS +
                 ' or any of ' + ', '.join(SOURCE_FALLBACK))
    print('   extracting %s from %s' % (', '.join(missing), source))
    with zipfile.ZipFile(source) as z:
        for n in missing:
            dst = os.path.join(SPLITS, n)
            with z.open(n) as s, open(dst, 'wb') as d:
                shutil.copyfileobj(s, d, 1 << 22)
            print('   + %s %s' % (n, format(os.path.getsize(dst), ',')))


def repack_arm(harness, dst):
    t = time.time()
    with zipfile.ZipFile(ARM_SRC) as zin, zipfile.ZipFile(dst, 'w', zipfile.ZIP_STORED) as zout:
        for info in zin.infolist():
            if info.filename.startswith('META-INF/'):
                continue    # stale v1 signature files from the source split
            if info.filename == ARM_ENTRY:
                data = open(harness, 'rb').read()
                zout.writestr(info.filename, data)
                print('   harness  %s bytes' % format(len(data), ','))
            else:
                zout.writestr(info, zin.read(info.filename))
    print('   arm repacked in %.1fs' % (time.time() - t))


def repack_base(dst):
    t = time.time()
    with zipfile.ZipFile(BASE_SRC) as zin, zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            path = BASE_REPLACE.get(info.filename)
            data = open(path, 'rb').read() if path else zin.read(info.filename)
            if path:
                print('   page     %-42s %s bytes' % (info.filename, format(len(data), ',')))
            zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            zi.compress_type = info.compress_type
            zi.external_attr = info.external_attr
            zout.writestr(zi, data)
        have = set(zin.namelist())
        for name, path in BASE_REPLACE.items():
            if name in have:
                continue
            zi = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_STORED if name.endswith('.jpg') else zipfile.ZIP_DEFLATED
            zout.writestr(zi, open(path, 'rb').read())
            print('   page     + %s %s bytes' % (name, format(os.path.getsize(path), ',')))
    print('   base repacked in %.1fs' % (time.time() - t))


def sign(raw, dst, label):
    aligned = raw + '.zipaligned'
    run([ZIPALIGN, '-p', '-f', '4', raw, aligned])
    run([JAVA, '-jar', APKSIGNER, 'sign', '--ks', KS, '--ks-pass', 'pass:' + KS_PASS,
         '--key-pass', 'pass:' + KS_PASS, '--ks-key-alias', ALIAS, '--min-sdk-version', '29',
         '--v1-signing-enabled', 'false', '--v2-signing-enabled', 'true',
         '--v3-signing-enabled', 'true', '--out', dst, aligned])
    run([JAVA, '-jar', APKSIGNER, 'verify', '--min-sdk-version', '29', dst])
    os.remove(raw)
    os.remove(aligned)
    for junk in (dst + '.idsig',):
        if os.path.exists(junk):
            os.remove(junk)
    print('   %s signed + verified (%s bytes)' % (label, format(os.path.getsize(dst), ',')))


def main():
    harness = sys.argv[1] if len(sys.argv) > 1 else 'work/cn/lab_startup.js'
    out_apks = sys.argv[2] if len(sys.argv) > 2 else None
    if not KS_PASS:
        sys.exit('set WZM_KS_PASS (with WZM_KS / WZM_KS_ALIAS) to your own signing key')
    for p in (ARM_SRC, BASE_SRC, harness):
        if not os.path.exists(p):
            sys.exit('missing ' + p)
    if not harness.endswith('.js') or os.path.getsize(harness) < 10000:
        sys.exit('harness looks wrong: ' + harness)
    head = open(harness, encoding='utf-8', errors='replace').read(400)
    if 'lab' not in head.lower():
        sys.exit('harness does not look like a lab build: ' + harness)
    os.makedirs(OUT, exist_ok=True)
    ensure_splits()

    arm = os.path.join(OUT, 'arm_signed.apk')
    base = os.path.join(OUT, 'base_signed.apk')
    print('[1/3] arm split')
    repack_arm(harness, os.path.join(OUT, 'arm_unsigned.apk'))
    sign(os.path.join(OUT, 'arm_unsigned.apk'), arm, 'arm')
    print('[2/3] base apk')
    repack_base(os.path.join(OUT, 'base_unsigned.apk'))
    sign(os.path.join(OUT, 'base_unsigned.apk'), base, 'base')
    print('[3/3] package')
    if out_apks:
        with zipfile.ZipFile(out_apks, 'w', zipfile.ZIP_STORED) as z:
            z.write(base, 'base.apk')
            z.write(arm, 'arm.apk')
            for n in FIXED:
                z.write(os.path.join(SPLITS, n), n)
        print('   -> %s (%s bytes)' % (out_apks, format(os.path.getsize(out_apks), ',')))
    print('\ninstall (in-place, keeps data):')
    print('  adb install-multiple -r --no-streaming %s %s %s %s %s' %
          (base, arm, os.path.join(SPLITS, 'en.apk'),
           os.path.join(SPLITS, 'xx.apk'), os.path.join(SPLITS, 'asset.apk')))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
