# Open-WZM-Next-3.10

面向 **Call of Duty: Warzone Mobile 3.10** 的个人离线工具链与静态分析笔记。
仓库里只有作者自己写的脚本、文档，以及针对**自己那份游戏安装包**跑出来的地址与统计结果。

本项目使用Deepseek v4.1 flash 1017辅助

> **先说清楚**
> 本仓库**不是游戏，也不包含任何游戏内容**：没有 APK / OBB / 资源包，没有 `libgame.so`，
> 没有签名密钥，也没有任何下载地址。它不能单独运行，必须配合你自己合法拥有的游戏副本。
> 请在本机离线使用，不要用于线上对局、商业用途或二次分发。

---

## 1. 它是什么 / 不是什么

| 是 | 不是 |
| --- | --- |
| 一套可复现的构建与校验脚本（Python + Node + JDK） | 游戏本体或拆分包 |
| 注入脚本的锚定补丁、启动页、调试通道说明 | 破解版、去校验版、联机版 |
| 引擎静态分析产物（函数边界、字符串交叉引用） | 任何可执行代码或游戏资源 |
| 一台已连设备上的本地排障 CLI | 绕过服务器授权或修改线上数据的工具 |

## 2. 功能面（全部在本机离线生效）

- **应用名**：桌面显示 `WZM3.10 Next`（重建 `resources.arsc` 字符串池，资源 id 不变）。
- **启动页**：自写的静态页（`assets/index_v31.html`），不联网、不加载远端资源。
- **本地对局配置**：模式 / 地图 / 队伍规模 / 人机难度，只写本机存档。
- **中文语言包**：调用游戏自带语言包的切换接口。
- **运行时诊断通道**：平时完全不写盘，收到命令才写一次 `out.json`，不挂在启动路径上。
- **贴图档位与线程调度**：默认**不修改**引擎配置；只有在显式开启时才动。

## 3. 目录

```
work/
  build.py            把注入脚本 + 启动页重新打进 .apks（需要自备拆分包与签名密钥）
  lab.py              设备 CLI：status / log / send / lua / texture / install / launch …
  lab_patch.py        补丁驱动：跑 patch_*.py 后过一遍 node --check
  patch_v22.py        旧版注入脚本的锚定补丁链（每条编辑都带断言）
  patch_v31.py        3.1 的「流送 dvar 回退」补丁：两个 dvar 只读不写
  verify_build.py     拆分包体检：包名 / 版本 / 签名 / 包内地图 / 锚点迁移率
  elf.py axml.py      ELF 与二进制 AndroidManifest 解析（纯 Python，无第三方依赖）
  anchors.json/.md    hook 锚点表（地址 + 首指令校验字）
  probe/sched_state.js  线程表探针：名字 / nice / 允许 CPU 列表（只读）
  tools/              逆向与比对小工具
    ehframe.py          .eh_frame_hdr → 函数边界表
    strxref.py          ADRP+ADD 扫描 → 字符串交叉引用
    xrefs.py            BL 立即数扫描 → 直接调用者
    names.py            按字符串给函数命名（capstone）
    report.py           汇总成分析报告
    jsdiff.py           JS 字符级差异（定位改动，不整文件刷屏）
    splitdiff.py        split APK 逐条目比对（容忍改名）
    apksdiff.py         .apks 两级差异
    xentry.py           从 zip 里取单个条目
    lua_check.py        Lua 结构检查（括号 / 块 / 越界 return）
    lua_extract.py      从注入脚本里抽出内嵌 Lua 再交给 lua_check
    apkinfo.py          单包信息
    label.py            改应用名：重建 resources.arsc 的字符串池（自带 aapt2 自检）
  analysis/           静态分析产物与笔记（见第 7 节）
assets/index_v31.html 启动页
docs/                 版本说明
```

## 4. 复现前提（需自备，仓库不提供）

1. 你自己合法获得的 **3.10 拆分包**：`base.apk`、`config.arm64_v8a`（含 `libgame.so`）、`asset_pack`、`config.en`、`config.xxhdpi`。
2. Python 3.10+、Node 18+（做 `node --check`）、JDK 17+（apksigner 用）。
3. Android build-tools 的 `apksigner.jar` 与 `zipalign`（`WZM_BUILD_TOOLS` 指向其目录）。
4. 一个属于你自己的签名密钥：`WZM_KS` / `WZM_KS_PASS` / `WZM_KS_ALIAS`。
5. 一台开了 USB 调试的设备（可选，用于装机与排障）。

## 5. 快速开始

```bash
# 0) 准备输入
#    work/cn/arm.apk         你的 arm64 split（含注入槽位）
#    work/cn/base.apk.orig   同版本未改动的 base
#    work/out/splits/        en.apk、xx.apk、asset.apk
#    work/tools/platform-tools/adb.exe   adb（或改 lab.py 里的 ADB）

# 1) 打补丁并检查语法
python work/patch_v31.py <升级前的注入脚本.js> work/cn/lab_startup.js

# 2) 打包
WZM_KS=release/your.keystore WZM_KS_PASS=*** \
  python work/build.py work/cn/lab_startup.js out.apks

# 3) 装机（就地升级，保留数据）
python work/lab.py install out.apks

# 4) 排障
python work/lab.py status        # 读一次 out.json
python work/lab.py log 200       # 事件日志尾巴
python work/lab.py send work/probe/sched_state.js
```

## 6. 包体检

```bash
python work/verify_build.py <拆分包目录 | *.apks | *.xapk>
```

输出 `work/verify_<tag>.md`：包名与 versionCode、每个 split 的签名来源、
`libgame.so` 的 buildinf、包内可离线地图、以及 43 个 `.text` 锚点在目标版本上的迁移率。

## 7. 逆向部分

**方法**（全部只用公开工具，可复现）：

1. `.eh_frame_hdr` 的二分搜索表给出 FDE 边界 → 反推函数起止，绕开 `.symtab` 被剥离的问题；
2. 线性扫描 `BL` 立即数得到直接调用关系（不依赖符号）；
3. 解析 `ADRP+ADD` 配对，把 `.rodata` 字符串关联到所属函数，用关键字反查可疑函数；
4. 关键函数用 capstone 反汇编后人工读，配合锚点表做版本迁移。

**产物**（`work/analysis/`）：

| 文件 | 内容 |
| --- | --- |
| `functions_310.csv` | 164,174 个函数：起始地址、长度 |
| `string_xrefs_310.csv` | 6,092 条字符串交叉引用：字符串地址、所属函数 |
| `libgame310-reverse.md` | 工具链、锚点映射、渲染/bot/Lua 区域索引 |
| `README.md` | 静态分析笔记（画质档位、渲染器结构、dvar 落点） |
| `libgame_310.symbols` + `ida_apply_symbols.py` / `ghidra_apply_symbols.py` | 已恢复符号，导入 IDA/Ghidra |
| `anchors.md` / `anchors.json` | 注入脚本实际 hook 的锚点全表 |
| `js_v30_v31.md` / `js_v31_revert.md` | 注入脚本两版的字符级差异（含 3.1 的回退依据） |
| `lab-harness-map.md` / `v16-observability.md` / `cdni-download.md` / `map_scan.txt` | 通道设计、CDNI 观察、包内地图清单 |

**没有随仓库分发的东西**：原始 `libgame.so`、反汇编清单（`.asm`）、资源包、注入脚本成品。
前两类涉及游戏代码，请用你自己的副本跑上面的工具现场生成；成品脚本请用补丁脚本重建。

**注意**：表里的地址只对 **3.10（changelist 19854920）** 有效，换了版本必须重跑，锚点会漂移。

## 8. 已知限制

- 表与锚点是静态产物，不保证跨版本可用；`verify_build.py` 会给迁移率。
- 只做本机离线；CDN/资源下载依赖游戏自身的逻辑，仓库不提供绕过。
- 8 GB 机型长时间对局内存吃紧，CLI 里保留了纹理档位与清理入口。
- 反汇编与分析是人工阅读，不保证语义完整；没有反编译器时只到"结构 + 交叉引用"。

## 9. 法律与免责

1. **非官方**：本项目与 Activision Publishing, Inc.、Raven Software、Treyarch、网易及其关联公司
   没有任何关系，未获其授权、认可或支持。所有商标、游戏名称、引擎与技术归各自权利人所有。
2. **不含版权内容**：仓库仅包含作者原创的脚本与文档，以及针对特定二进制偏移的事实性数据
   （函数起止地址、字符串交叉引用、符号名）。这些数据不含游戏代码或资源，且随版本失效，
   需由使用者用自己的副本重新生成。
3. **用途限制**：仅限在你自己合法拥有的游戏副本上做本机离线研究、备份与排障。
   禁止用于商业用途、二次分发、线上对局，禁止用于绕过付费内容或服务器校验。
4. **风险自负**：修改安装包可能导致存档损坏、设备异常或账号被平台处罚。作者不承担任何责任，
   不提供任何明示或默示担保；使用即表示你接受这一条。
5. **地区差异**：不同司法辖区对逆向工程与软件修改的规定不同。若你所在地区不允许，请勿使用。
6. **移除承诺**：若权利人认为本仓库某部分不妥，请通过 Issue 说明，核实后立即删除相关内容。

## 10. 许可与致谢

- 脚本与文档：MIT（见 `LICENSE`）。游戏相关内容不在本许可范围内。
- 分析数据（CSV / 符号表）：按"现状"提供，仅作研究记录。
- 致谢：Frida（gadget 运行时）、LLVM / capstone（反汇编）、Android build-tools（签名与对齐）。
