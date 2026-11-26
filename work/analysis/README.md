# libgame.so 3.10 静态分析笔记（供 IDA / Ghidra 使用）

目标文件：`work/libs/orig_libgame.so`（91,196,224 B，原版未改；`liblab.clean.so` 与它逐字节相同）
构建：changelist 19854920 · `mgl-release` · depot `iw9` · 2024-09-11
格式：ELF64 ARM64，**无 .symtab**（只剩 471 个导出符号），无字符串化 dvar 名。

配套产物：
- `work/analysis/libgame_310.symbols` — 68 个已恢复符号（`0x地址 名字`）
- `work/analysis/ida_apply_symbols.py` — IDA 里 File → Script file 直接跑
- `work/analysis/ghidra_apply_symbols.py` — Ghidra Script Manager 里跑（Jython）
- `work/anchors.md` — 注入脚本实际 hook 的 56 个锚点全表（含首指令校验字）

载入方法：IDA 里 File → Script file 选 `ida_apply_symbols.py`；Ghidra 里 Script Manager → Python(Jython) → 选 `ghidra_apply_symbols.py`。

---

## 1. 设备档位（quality tier）—— 画质的总开关

这是这次分析最有价值的发现。

**存储位置**：`[g_renderer] + 0xe97c`，u32，取值 0–8。

```
g_renderer       0x5657488   (.got 槽位，指向 renderer 单例)
   renderer+0x488  → 单例本体
   +0xe97c         → tier
```

**判定函数**：`0x2854a30`（`gpu_support_check`）
它先把一个 0xffe 字节的设备属性结构拷到栈上（`bl 0x550ea60`），然后：

```
mov w9, #0xe97c
ldr w9, [x8, x9]        ; tier = renderer->tier
cmp w9, #8
b.hi  -> 返回 1（支持）
adrp x10,#0x5e8000 ; add x10,x10,#0x58b   ; 9 字节跳转表
ldrb w12,[x10,x9]
add  x11,x11,w12,lsl #2
br   x11
```

跳转表 `0x5e858b` 的 9 个字节：

| tier | 字节 | 落点 | 结果 |
|---|---|---|---|
| 0 | 34 | 0x2854b24 | 支持 |
| 1 | 0 | 0x2854a9c | 查设备属性，可能不支持 |
| 2 | 20 | 0x2854aec | 查驱动字符串，可能不支持 |
| 3 | 14 | 0x2854ad4 | **直接返回 1（支持）** |
| 4 | 29 | 0x2854b10 | 另有一组检查 |
| 5/6/7 | 14 | 0x2854ad4 | 直接支持 |
| 8 | 34 | 0x2854b24 | 支持 |

改版脚本在 `0x19ea3d0` 与 `0x15ab9ac` 两个调用点把返回值强制改成 1，就是绕过这里。

**档位是谁写入的**：`0x2e0d354`（`gpu_tier_classify`）里按 GPU 厂商 ID 分支：

```
cmp w9,#0x13b5 (ARM)      -> tier = 1
cmp w9,#0x5143 (Qualcomm) -> tier = 2
cmp w9,#0x1010 / 0x144d (Samsung) ...
```

**读 tier 的 12 个函数**（这些就是"按档位开不同画质"的地方，值得逐个看）：

```
0x1283004  0x1283970  0x1283d5c  0x1873524  0x18aaf18  0x18b4e8c
0x18b5958  0x2854a30  0x2e0d354  0x2e101f4  0x2e160f8  0x42f9318
```

**可做的实验**（需真机）：
1. 在 renderer 初始化后把 `+0xe97c` 写成 3/5/6/7（这几个 tier 直接返回"支持"），看画质选项/帧率是否变化；
2. 或者 hook `gpu_tier_classify`，把厂商 ID 换成高端机型的组合。

> 风险：tier 还会影响显存预算、纹理流送档位，写错可能 OOM 或闪退，必须一次改一档、进图观察。

---

## 2. 纹理 / 画质链路（改版已用到的一部分）

| 地址 | 名称 | 说明 |
|---|---|---|
| `0xab5abe8` | `dvar_picmip_ptr` | 指向 picmip 的 dvar 结构体；结构体 `+0x28` 是当前整数值 |
| `0xc038170` | `dvar_stream_http_ptr` | `stream_http`（HTTP 流送） |
| `0xc0bd628` | `dvar_stream_http_prefetch_ptr` | `stream_http_prefetch_enabled` |
| `0x19e6690` | `texture_picmip_update` | 函数：更新 picmip |
| `0x19e66fc` | `texture_picmip_normalize_site` | 单条指令，原值 `0x1a940133`（`csel w19,w9,w20,eq`），被改成 `0x2a1403f3`（`mov w19,w20`）就不再被游戏拍回低档 |
| `0x143b1a8` | `dvar_value_apply` | 改版 hook 它来替换写入值 |
| `0x143e700` | `dvar_set_value` | **按 dvar 类型分派的官方 setter**（`ldrb w8,[x0,#0x15]` 取类型，跳转表 `0x570c2a`）。设置项要生效，应该走它 |
| `0x143e640` | `dvar_set_flag_path` | 另一个 setter 变体（跳转表 `0x570c1f`） |
| `0x143e640` 附近 | — | 两者都会走 `0x1443974`（引擎错误上报） |

**这解释了 `计划.txt` 里 3121 只有 3/10 生效**：直接写 dvar 结构体 `+0x28` 不会触发变更通知；必须调 `0x143e700`（或 Lua 侧 `Dvar` 的 set，哈希 `2414681ecab880f`）才会让渲染侧收到。

**可做的实验**：用 `0x143e700` 写 picmip 之外的其他项（先要拿到它们的 dvar 指针），观察是否立即生效。

---

## 3. Lua 字符串池（3.10 特有的大补丁）

| 地址 | 名称 |
|---|---|
| `0xc6ffd60` | `g_lua_string_pool`（13.6 MB arena，0xd00000） |
| `0xc67fd58` | `g_lua_pool_meta` |
| `0xc67fcb4` | `g_lua_pool_counter` |
| `0x259afc4` | `lua_pool_alloc` |
| `0x259b634` | `lua_pool_free` |
| `0x259ba18` | `lua_pool_resize` |

改版用 CModule 把这三个函数整体替换掉，并 patch 了 47 个分配访问点（`0x259400c`–`0x25ab4b0`）。**如果 v2/v3 把装备记录控制住，这一层其实可以不做**——它是最容易引发奇怪崩溃的一块。

---

## 4. dvar 名字是哈希过的

在 `.rodata` 里只找到 103 个 `xxx_yyy` 形态的字符串，**没有** `picmip` / `r_renderScale` / `com_maxfps` / `vsync` 这类常见 dvar 名；全文件搜 `picmip` 也是 0 次。说明 3.10 的 dvar 名在构建期被换成 `#x<16 hex>`。

推论：**不可能靠字符串静态枚举 dvar**。要拿设置项，只能在运行时从 dvar 结构体 `+0x00`（name 指针）读出来——这也是下一步实验要做的。

---

## 5. 建议的下一步（都需要真机）

| 优先级 | 实验 | 预期收益 | 失败代价 |
|---|---|---|---|
| P0 | 用 `0x143e700` 写 picmip，对比直接写内存 | 验证"setter 路径"，为所有设置项铺路 | 无（可回滚） |
| P0 | 读 `renderer+0xe97c` 当前值，再试写 3/5/7 | 可能解锁高画质档 | 闪退 / OOM |
| P1 | 从 dvar 结构体读 name，拼出 `#x…` 清单 | 得到可用的设置项全集 | 无 |
| P2 | 研究 tier 读取最多的 `0x2e101f4`（3 处） | 找到画质预设表 | — |

---

## 6. 说明

- 所有地址都是 **vaddr**（Frida 的 `Module.base + offset` 语义），不是文件偏移；两者在 `.text` 段相差 0x1000。
- 反汇编用 capstone 线性扫描得到，函数起点是启发式（向前找 `stp x29,x30,[sp,#-N]!` / `sub sp,sp,#N`），个别可能偏几条指令，用符号时以语义为准。
- 这份笔记只覆盖与"画质/性能"相关的路径；对局、bot、护甲那些在 `WZM3.10离线版-玩法层拆解.md` 里已有完整清单。