"""Compose work/analysis/libgame310-reverse.md from the generated artifacts."""
import bisect
import collections

BT = chr(96)

def q(s):
    return BT + s + BT

ANCHORS = [
    ("0x47ded18", "Lua 入口（UI 桥调用）"),
    ("0x47d2fa4", "Lua debug 控制台 handler"),
    ("0x143e700", "dvar 官方 setter"),
    ("0x143b1a8", "dvar apply hook"),
    ("0xf28f20", "资源路径 hook"),
    ("0x19e66fc", "纹理归一化点"),
    ("0x2854a30", "GPU 兼容判定"),
    ("0x3f2e1c4", "bot 动作脚本钩子"),
    ("0x479b298", "bot 瞄准状态机"),
    ("0x47a56a8", "bsparam 行为参数表"),
    ("0x1db4d30", "玩家卡结构（isBot/team）"),
]

def load():
    starts, sizes = [], {}
    for line in open("work/analysis/functions_310.csv", encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("addr"):
            continue
        a, s = line.split(",")
        a = int(a, 16)
        starts.append(a)
        sizes[a] = int(s)
    return sorted(starts), sizes

def load_strings():
    per_fn = collections.defaultdict(list)
    for line in open("work/analysis/string_xrefs_310.csv", encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("string_addr"):
            continue
        parts = line.split(",")
        if len(parts) < 3:
            continue
        fn = int(parts[-1], 16)
        per_fn[fn].append(",".join(parts[1:-1]).strip(chr(34)))
    return per_fn

def main():
    starts, sizes = load()
    per_fn = load_strings()
    rows = []
    for addr, label in ANCHORS:
        a = int(addr, 16)
        idx = bisect.bisect_right(starts, a) - 1
        fn = starts[idx] if idx >= 0 else a
        names = per_fn.get(fn, [])
        shown = ", ".join(q(s) for s in names[:4]) if names else "-"
        rows.append("| %s | %s | 0x%x | %d | %d | %s |" % (addr, label, fn, sizes.get(fn, 0), len(names), shown))
    body = [
        "# libgame.so 3.10 (arm64) 逆向记录",
        "",
        "本文件由 work/tools/report.py 生成，数据全部来自工具链输出。",
        "",
        "## 工具链",
        "- LLVM 29 (Android NDK): llvm-readelf / llvm-objdump —— ELF 结构、反汇编",
        "- capstone 5 (python) + 自写脚本 —— 函数边界、直接调用关系、字符串交叉引用",
        "- 本机没有 IDA / Ghidra / radare2（注册表与 Program Files 均查过），走 LLVM + capstone 路线",
        "",
        "## 样本",
        "- work/libs/orig_libgame.so：91,196,224 B，ELF64 aarch64 DYN，BIND_NOW，26 个 section",
        "- .text 0xec4000 约 73.6 MB；.rodata 2.9 MB；.bss 158 MB；.eh_frame 6.0 MB",
        "- 导出符号只有 474 个（全是 libc 导入），.symtab 已剥",
        "",
        "## 函数边界",
        "剥符号不等于没有函数表：.eh_frame_hdr 是一张按地址排序的 FDE 表。",
        "- 表项 185,959 条，全部解码成功，落在 .text 内 164,174 个函数",
        "- 大小由相邻起点推导：最小 4 B，中位数 120 B",
        "- 产出 work/analysis/functions_310.csv",
        "",
        "## 调用关系",
        "直接调用用 BL 立即数扫描（线性遍历 .text 的 18M 条指令字），不受剥符号影响。",
        "- dvar setter 0x143e700 有 60 个直接调用者；dvar apply 0x143b1a8 有 15 个；资源路径 hook 0xf28f20 有 15 个",
        "- 工具 work/tools/xrefs.py + work/analysis/targets.txt",
        "",
        "## 字符串交叉引用",
        "ADRP+ADD 配对解析，把每个被引用字符串定位到所在函数：",
        "- 6,092 条 → work/analysis/string_xrefs_310.csv（string_addr,string,func_addr）",
        "- 这是后续定位任何子系统的入口：按关键字反查函数即可",
        "",
        "## 已知锚点 → 所在函数",
        "",
        "| 锚点 | 含义 | 函数起点 | 大小 | 字符串数 | 部分字符串 |",
        "|---|---|---|---|---|---|",
    ] + rows + [
        "",
        "## Bot AI",
        "- 0x479b298（281 条字符串）：aim_state / aim_active / aim_yaw / aim_pitch / aim_yaw_delta /",
        "  bot_difficulty_updated —— bot 瞄准状态机，难度生效点",
        "- 0x47a56a8（609 条字符串）：50 个 bsparam_* 行为参数（ladder/mantle/mount/vehicle/turret/slope/melee/weapon_occlusion），",
        "  是角色程序化动作参数表，不是战斗 AI；其中 bsparam_weapon_occlusion_adjust 与命中相关",
        "- 0x3f2e1c4：bot_activate / bot_jump / bot_ladder / bot_move_forward，bot 动作下发点",
        "- 0x1db4d30：玩家卡结构（isBot/team/isMuted），不是 AI",
        "- 下一步：在运行时确认 0x479b298 用到的名字是否为 dvar，再决定改 dvar 还是改常量表",
        "",
        "## Lua 运行时",
        "- 解释器集中在 0x47d0000 附近：0x47d2fa4 引用 lua_debug> 与 =(debug command)，是调试控制台 handler",
        "- 0x47de9cc 是 UI 桥入口（1,304 B），直接调用者 6 个，其中 3 个在 0x47d2fa4~0x47d6d34 这段",
        "- 反汇编在 work/analysis/disasm/",
        "",
        "## 复现",
        q("python work/tools/ehframe.py work/libs/orig_libgame.so work/analysis/functions_310.csv"),
        q("python work/tools/strxref.py work/libs/orig_libgame.so work/analysis/string_xrefs_310.csv"),
        q("python work/tools/xrefs.py work/libs/orig_libgame.so work/analysis/targets.txt"),
        q("python work/tools/names.py work/libs/orig_libgame.so 0x479b298,0x47a56a8"),
        q("python work/tools/report.py"),
        "",
    ]
    open("work/analysis/libgame310-reverse.md", "w", encoding="utf-8").write(chr(10).join(body))
    print("wrote work/analysis/libgame310-reverse.md")

if __name__ == "__main__":
    main()