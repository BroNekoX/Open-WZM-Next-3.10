# 注入脚本结构图（lab_startup_v3.js，1,392 行 / 122,647 B）

改这个脚本前先看这张表：**行号 + 职责 + 改动风险**。行号对应 `work/cn/lab_startup_v3.js`；改完必须过 `node --check`，再走 `work/build_apks.py` 重新打包。

## 分区

| 行 | 区块 | 做什么 | 改动风险 |
|---|---|---|---|
| 1 | 路径常量 | `dir` = 应用外部目录 | 低 |
| 3–34 | **lab config**（v3 新增） | `LAB_MEDIA` / `LAB_CFG`（读 config.json）/ `labRead()` | 低 |
| 36–69 | **装备存档** | 读 `local-equipment.json` → `labSavedEquipmentLua`；`labSaveEquipment()` 原子写 | 中（格式一改，旧存档失效） |
| 71–179 | **反篡改层** | JNI 证书替换、`open` 重定向到 `liblab.clean/original.so`、线程改名 | **高**（动错=被反作弊杀或读不到资源） |
| 181–191 | 模块观察者 | 等 `libgame.so` 加载后进入主安装流程 | 低 |
| 193–230 | GPU 兼容闸门 | 把 `0x2854a30` 的返回值在两条调用点改成 1 | 中 |
| 234–509 | 字符串池重写 | `labInstallCompactPool`：CModule 替换 `0x259afc4/free/resize` + 47 个访问点 | **高**（最容易出怪崩溃） |
| 511–515 | 池安装调用 | v2 起包了 try/catch | 低 |
| 518–526 | 场景门 | patch `0x12ee484` + hook `0x134febc` | 中 |
| 528–564 | 护甲规则 | CModule 重写 `helmet_rule`（DDL 接口） | 中 |
| 566–633 | 固定分队/传送 | hook `0x407ff18` + `0x40789c0` | 中 |
| 635–664 | 倒地保护 | 手写 ARM64 stub 替换 `0x40a4a90` | 中 |
| 666–696 | 倒地视角 | 替换 `0x458de38` 的一条指令 | 中 |
| 698–1186 | **BR bot 发枪** | 落地 15s 后发枪 + 输入命令改写 | 中（只影响 BR） |
| 1188–1216 | **开局** | `lab310CreateMatch()`：取 party、起本地对局 | **高**（改错开不了局） |
| 1218–1232 | 战利品表别名 | `0xf28f20` 路径替换 | 低 |
| 1234–1311 | 纹理档位 | `createTextureQualitySetter`：patch `0x19e66fc` + hook `0x143b1a8` + `setInt` | 中 |
| 1313–1333 | **注入的 Lua** | `defaultLua`：菜单、选图、开局规则、装备持久化（约 34 KB，字符串形式） | **高**（Lua 语法错误=整条链失效） |
| 1335–1392 | **Lua 桥 + 指令通道** | 每 1.5s 注入 Lua、每 1s 轮询 request、`applyBootConfigOnce()`、会话清理 | 中 |

## 改动约定

1. **只加不改**：新功能尽量作为独立块追加，并在开头用 `try{}catch(e){log('feature-skip',…)}` 包住；
2. **每个 hook 前都断言指令字**（现有代码都这么做，如 `if(target.readU32()!==0xd100c3ff)throw…`），这样版本不对会跳过而不是崩；
3. **日志事件保持短横线命名**，需要排障时把 `diag` 打开；
4. **调参走 config.json**，不要为新阈值改代码——v3 已把 `tier/texture/cleanupMs/diag` 四个口子开出来；
5. 改完三步验证：`node --check` → `python work/build_apks.py <js> <out.apks>` → 装机看 `lab310.jsonl`。

## 关键常量（改之前先确认版本）

| 常量 | 值 | 位置 |
|---|---|---|
| `g_renderer` | `0x5657488` | v3 config 档位写入 |
| renderer 档位字段 | `+0xe97c` | 同上 |
| picmip dvar 指针 | `0xab5abe8` | 纹理档位 |
| picmip 归一化指令 | `0x19e66fc`（`0x1a940133` ↔ `0x2a1403f3`） | 纹理档位 |
| dvar 官方 setter | `0x143e700` | 设置项改造（未用） |
| Lua 池 | `0xc6ffd60` / `0x259afc4` / `0x259b634` / `0x259ba18` | 池重写 |
| Lua 执行入口 | `0x47ded18` | 注入桥 |

完整地址表见 `work/analysis/libgame_310.symbols` 与 `work/analysis/README.md`。