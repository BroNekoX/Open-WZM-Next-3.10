"""Pull one entry out of a zip (bundle -> split apk, split apk -> lib).

    python work/tools/xentry.py <zip> <entry> <outfile>
"""
import os
import shutil
import sys
import zipfile


def main(zip_path, entry, out):
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        info = z.getinfo(entry)
        with z.open(info) as s, open(out, 'wb') as d:
            shutil.copyfileobj(s, d, 1 << 22)
    print('%-52s %s B -> %s' % (entry, format(os.path.getsize(out), ','), out))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main(sys.argv[1], sys.argv[2], sys.argv[3])
