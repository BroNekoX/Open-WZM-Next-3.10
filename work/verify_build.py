"""One-command triage for a Warzone Mobile split set, against the 3.10 lab.

    python work/verify_build.py <dir with splits | *.apks | *.xapk>

Stages
  1. unpack / inventory      - which splits, package, versionCode
  2. libgame.so triage       - buildinf, DT_SONAME (7-byte injection viable?), markers
  3. map inventory           - merged_<zone> bundles = maps playable offline
  4. anchor relocation       - how many of the 3.10 lab's 43 code anchors still match
Writes work/verify_<tag>.md and prints a verdict.
"""
import json
import os
import re
import struct
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from elf import ELF
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM
from axml import decode

REF_LIB = 'work/libs/libgame.so'
REF_ANCHORS = 'work/anchors.json'
OUT_DIR = 'work'
N_INSNS = 48
CHUNK = 1 << 22

md = Cs(CS_ARCH_ARM64, CS_MODE_ARM)
md.detail = True


# ---------------------------------------------------------------- helpers ----

def unpack_splits(path, tag):
    """Return (dir, [apk paths]) for a dir / .apks / .xapk / single .apk."""
    if os.path.isdir(path):
        apks = sorted(os.path.join(path, f) for f in os.listdir(path) if f.endswith('.apk'))
        return path, apks
    out = os.path.join(OUT_DIR, 'splits_' + tag)
    os.makedirs(out, exist_ok=True)
    with zipfile.ZipFile(path) as z:
        inner = [n for n in z.namelist() if n.endswith('.apk')]
        if not inner:                      # a single split apk
            return os.path.dirname(os.path.abspath(path)), [path]
        for n in inner:
            dst = os.path.join(out, os.path.basename(n))
            if os.path.exists(dst) and os.path.getsize(dst) == z.getinfo(n).file_size:
                continue
            with z.open(n) as s, open(dst, 'wb') as d:
                while True:
                    b = s.read(CHUNK)
                    if not b:
                        break
                    d.write(b)
    return out, sorted(os.path.join(out, f) for f in os.listdir(out) if f.endswith('.apk'))



def signer_info(apk):
    """Is this an untouched Play bundle, or a repack? (bundletool + Activision cert)"""
    try:
        with zipfile.ZipFile(apk) as z:
            names = z.namelist()
    except Exception:
        return {'official': False, 'why': 'unreadable'}
    bndl = any(n.startswith('META-INF/BNDLTOOL') for n in names)
    with open(apk, 'rb') as f:
        f.seek(0, 2)
        size = f.tell()
        tail_len = min(size, 1 << 20)
        f.seek(size - tail_len)
        tail = f.read()
        i = tail.rfind(b'PK\x05\x06')
        if i < 0:
            return {'official': False, 'why': 'no EOCD'}
        cdoff = struct.unpack_from('<I', tail, i + 16)[0]
        start = max(0, cdoff - (4 << 20))
        f.seek(start)
        blob = f.read(max(0, cdoff - start))
    act = b'Activision' in blob
    if bndl and act:
        return {'official': True, 'why': 'BNDLTOOL + Activision cert'}
    why = []
    if not bndl:
        why.append('无 META-INF/BNDLTOOL（被重打包）')
    if not act:
        why.append('签名证书里没有 Activision')
    return {'official': False, 'why': ', '.join(why) or 'unknown'}


def manifest_of(apk):
    with zipfile.ZipFile(apk) as z:
        try:
            return decode(z.read('AndroidManifest.xml'))
        except KeyError:
            return ''


def attrs(line):
    return dict(re.findall(r'([a-zA-Z_.:]+)="([^"]*)"', line))


def norm_tokens(elf, vaddr, n=N_INSNS):
    off = elf.vaddr_to_offset(vaddr)
    if off is None:
        return []
    out = []
    for ins in md.disasm(elf.data[off:off + n * 4], vaddr):
        ops = []
        for op in ins.operands:
            if op.type == 1:                        # register
                r = ins.reg_name(op.reg) or '?'
                ops.append('R' + (r[0] if r else '?'))
            elif op.type == 2:                      # immediate
                ops.append('I')
            elif op.type == 3:                      # memory
                m = op.mem
                ops.append('M%s' % (ins.reg_name(m.base) or '-')[:2])
            else:
                ops.append('?')
        out.append(ins.mnemonic + ':' + ','.join(ops))
        if len(out) >= n:
            break
    return out


def token_score(a, b):
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    same = sum(1 for i in range(n) if a[i] == b[i])
    return same / max(len(a), len(b))


def _find_all(data, needle, limit=3000):
    out, start = [], 0
    while len(out) < limit:
        i = data.find(needle, start)
        if i < 0:
            break
        out.append(i)
        start = i + 1
    return out


def find_anchor(target, ref, ref_off, ref_tokens):
    """Adaptive-length prologue search + normalized token scoring.

    Common prologues ("stp x29,x30,[sp,#-0x20]!") occur thousands of times, so
    the needle is grown 16 -> 24 -> 32 bytes until the candidate set is small.
    """
    cands, nlen = [], 16
    for nlen in (16, 24, 32):
        cands = _find_all(target.data, ref.data[ref_off:ref_off + nlen])
        if len(cands) <= 400:
            break
    scored = []
    for off in cands:
        v = None
        for p in target.segments:
            if p['type'] == 1 and p['offset'] <= off < p['offset'] + p['filesz']:
                v = p['vaddr'] + (off - p['offset'])
                break
        if v is None:
            continue
        scored.append((token_score(ref_tokens, norm_tokens(target, v)), v))
    scored.sort(key=lambda x: -x[0])
    return (scored[0] if scored else (0.0, None)), len(cands), scored[:3]


# ------------------------------------------------------------------ main ----

def main(path):
    tag = os.path.basename(os.path.abspath(path)).replace('.apks', '').replace('.xapk', '')
    tag = re.sub(r'[^A-Za-z0-9_.-]', '_', tag)[:40] or 'build'
    split_dir, apks = unpack_splits(path, tag)
    lines = [f"# 构建体检报告 · {tag}", ""]

    # 1. inventory -----------------------------------------------------------
    problems = []
    pkgs, vcodes, splits = set(), set(), {}
    for a in apks:
        m = manifest_of(a)
        at = attrs(m.splitlines()[0]) if m else {}
        pkg = at.get('package', '?')
        vc = at.get('versionCode', '?')
        sp = at.get('split', 'base')
        pkgs.add(pkg)
        vcodes.add(vc)
        splits[sp] = (os.path.basename(a), os.path.getsize(a))
    lines += ["## 1. 包结构", "", "| split | 文件 | 大小 | 官方签名 |", "|---|---|---|---|"]
    for sp, (fn, sz) in sorted(splits.items()):
        info = signer_info(os.path.join(split_dir, fn))
        mark = '✅ 原版' if info['official'] else '⚠️ ' + info['why']
        lines.append(f"| `{sp}` | {fn} | {sz:,} | {mark} |")
        if not info['official']:
            problems.append(f"{fn} 不是官方原包（{info['why']}）")
    lines += ["", f"package: `{'`, `'.join(sorted(pkgs))}`  ·  versionCode: `{'`, `'.join(sorted(vcodes))}`", ""]
    if len(pkgs) != 1:
        problems.append("多个 split 的 package 不一致")
    if len(vcodes) != 1:
        problems.append("versionCode 不一致（split 必须同版本）")
    for need in ('base', 'config.arm64_v8a', 'asset_pack'):
        if need not in splits:
            problems.append(f"缺少 split: {need}")

    # 2. libgame.so ----------------------------------------------------------
    lib_apk = next((os.path.join(split_dir, v[0]) for k, v in splits.items()
                    if k.startswith('config.arm64')), None)
    elf = None
    if lib_apk:
        with zipfile.ZipFile(lib_apk) as z:
            cand = [n for n in z.namelist() if n.endswith('libgame.so')]
            if cand:
                dst = os.path.join(OUT_DIR, f'libgame_{tag}.so')
                if not os.path.exists(dst) or os.path.getsize(dst) != z.getinfo(cand[0]).file_size:
                    with z.open(cand[0]) as s, open(dst, 'wb') as d:
                        while True:
                            b = s.read(CHUNK)
                            if not b:
                                break
                            d.write(b)
                elf = ELF(dst)
                elf.parse_dynamic()
    lines += ["## 2. libgame.so", ""]
    if elf:
        lines.append(f"size `{len(elf.data):,}`  ·  DT_NEEDED `{elf.needed}`  ·  DT_SONAME `{elf.soname!r}`")
        bi = elf.section('buildinf')
        if bi:
            raw = elf.data[bi['offset']:bi['offset'] + bi['size']].rstrip(b'\0')
            info = {}
            for f in raw.split(b'\x1e'):
                if b'\x1f' in f:
                    k, v = f.split(b'\x1f', 1)
                    info[k.decode('latin1')] = v.decode('latin1')
            keep = ('changelist', 'p4branch', 'p4depot', 'timestamp')
            lines.append('buildinf: ' + '  ·  '.join(f"`{k}={info[k]}`" for k in keep if k in info))
        markers = {
            b'PLAYERSTATS_OFFLINE': 'offline stats (Fences)',
            b'updategamerprofile': 'local-mode dvar cmd',
            b'lui_': 'Lua UI bindings',
            b'mp_mgl_escape4': 'default BR zone ref',
            b'passPreloginFence': 'bootstrap bridge: prelogin',
            b'isCDNIFinished': 'bootstrap bridge: CDNI',
            b'closeWebView': 'bootstrap bridge: close',
            b'sysReady': 'bootstrap bridge: ready',
        }
        lines += ["", "| marker | 命中 | 含义 |", "|---|---|---|"]
        for m, why in markers.items():
            n = elf.data.count(m)
            lines.append(f"| `{m.decode()}` | {n} | {why} |")
        if not elf.soname:
            problems.append("libgame.so 没有 DT_SONAME（7 字节注入法不可直接用）")
    else:
        problems.append("没找到 libgame.so")
    lines.append("")

    # 3. map inventory -------------------------------------------------------
    lines += ["## 3. 包内地图（可离线）", ""]
    pack_apk = next((os.path.join(split_dir, v[0]) for k, v in splits.items()
                     if k == 'asset_pack'), None)
    bundles = []
    if pack_apk:
        with zipfile.ZipFile(pack_apk) as z:
            shards = [i for i in z.infolist() if i.filename.endswith('.shard')]
            pat = re.compile(rb'merged_[A-Za-z0-9_]{3,60}')
            seen = {}
            for info in shards:
                with z.open(info) as f:
                    prev = b''
                    while True:
                        b = f.read(CHUNK)
                        if not b:
                            break
                        buf = prev + b
                        for m in pat.finditer(buf):
                            seen.setdefault(m.group().decode('latin1'), info.filename)
                        prev = buf[-160:]
            bundles = sorted(seen)
            lines.append(f"shards: {len(shards):,}  ·  {sum(i.file_size for i in shards):,} bytes")
            lines.append("")
            maps = [b for b in bundles if re.match(r'merged_(mp|br)_', b)]
            trash = [b for b in bundles if b not in maps]
            for b in maps:
                lines.append(f"- `{b}`")
            if trash:
                lines.append(f"\n其它非地图 bundle（共享层/噪声）：{len(trash)} 个")
    lines.append("")

    # 4. anchor relocation ---------------------------------------------------
    lines += ["## 4. 锚点迁移（对 3.10 的 43 个 .text 锚点）", ""]
    total = hit = strong = 0
    rows = []
    if elf and os.path.exists(REF_LIB) and os.path.exists(REF_ANCHORS):
        ref = ELF(REF_LIB)
        anchors = json.load(open(REF_ANCHORS))
        for k, rec in sorted(anchors.items(), key=lambda kv: int(kv[0], 16)):
            v = int(k, 16)
            if not (0xec4000 <= v < 0x550e9c4):        # 3.10 .text
                continue
            total += 1
            ref_tok = norm_tokens(ref, v)
            off = ref.vaddr_to_offset(v)
            pro = ref.data[off:off + 16]
            (sc, addr), ncand, top3 = find_anchor(elf, ref, off, ref_tok)
            if sc >= 0.9:
                hit += 1
                strong += 1
            elif sc >= 0.6:
                hit += 1
            rows.append((k, rec['words'][0] if rec.get('words') else '', sc, addr, ncand, top3))
    for k, w, sc, addr, nc, top3 in rows:
        mark = '✅' if sc >= 0.9 else ('🟡' if sc >= 0.6 else '❌')
        alts = ', '.join(hex(a) for s2, a in top3[1:] if s2 >= 0.9)
        note = f" (+{alts})" if alts else ''
        lines.append(f"| {mark} | `{k}` | `{w}` | {sc:.2f} | {hex(addr) if addr else '-'}{note} | {nc} |")
    if rows:
        lines.insert(len(lines) - len(rows),
                     "| | 3.10 | 首指令 | 相似度 | 目标地址 | 候选数 |")
        lines.insert(len(lines) - len(rows), "|---|---|---|---|---|---|")
    lines.append("")

    # verdict ---------------------------------------------------------------
    lines += ["## 5. 结论", ""]
    if problems:
        lines.append("**包结构问题：**")
        for p in problems:
            lines.append(f"- {p}")
        lines.append("")
    mp = [b for b in bundles if b.startswith('merged_mp_') and 'frontend' not in b]
    if mp:
        lines.append(f"- 包内可离线对局 zone：**{len(mp)}** 个 → {', '.join(mp)}")
    if total:
        ratio = strong / total
        lines.append(f"- 锚点强匹配 **{strong}/{total}**（{ratio:.0%}）")
        if ratio >= 0.8:
            lines.append("- 判定：**可以直接移植**，缺的少数锚点手工补（Ghidra/Diaphora）")
        elif ratio >= 0.5:
            lines.append("- 判定：**可做**，但需逐个补锚点，工作量中等偏上")
        else:
            lines.append("- 判定：结构变化大，移植成本接近重写，建议换基线版本")

    out = os.path.join(OUT_DIR, f'verify_{tag}.md')
    open(out, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    print(f"\n[report] {out}")


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main(sys.argv[1] if len(sys.argv) > 1 else 'work/out/splits')