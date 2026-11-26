"""Print identity of an APK: package, versions, sdk, split, permission count, key certs."""
import sys, zipfile, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import axml

KEYS = ("package", "versionCode", "versionName", "compileSdkVersion", "platformBuildVersionCode", "split", "configForSplit")

def info(path):
    z = zipfile.ZipFile(path)
    xml = axml.decode(z.read("AndroidManifest.xml"))
    print("==", os.path.basename(path), "(%d bytes)" % os.path.getsize(path))
    for line in xml.splitlines():
        s = line.strip()
        if s.startswith("<manifest") or s.startswith("<uses-sdk"):
            print("  " + s[:400])
    print("  perms:", xml.count("<uses-permission"), "| activities:", xml.count("<activity"),
          "| libs:", [n for n in z.namelist() if n.endswith(".so")][:8])
    z.close()

for p in sys.argv[1:]:
    info(p)
