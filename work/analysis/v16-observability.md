# v16：运行时可观测性（按需导出）

## 为什么要这么设计

| 通道 | 读取 | 写入 | 结论 |
|---|---|---|---|
| 应用私有目录 /data/user/0/<pkg>/files/ | 只能进程内 | 只能进程内 | 唯一安全区，但 adb 看不到 |
| /sdcard/Android/data/<pkg>/files/ | adb 被拒（Android 13+） | adb 被拒 | 只能存内部日志 |
| /sdcard/Android/media/<pkg>/ | **adb 可读可写** | 会走 FUSE | 启动阶段写入会卡死 CDNI 校验（v3~v9 的 0/2） |

所以：**输入用系统属性，输出只在收到指令后写一次 media**。

## 通道

```
adb shell setprop debug.wzm.cmd <id>          # 触发（属性读取，零文件 IO）
/sdcard/Android/media/<pkg>/cmd.json          # 载荷，仅在触发后才读
/sdcard/Android/media/<pkg>/out.json          # 结果，每条指令只写一次
```

安全性由代码保证：

* 45 s 后才武装；武装瞬间把属性当前值记为"已见"，历史遗留值不会触发命令；
* 120 s 之前**完全不碰 media**（连 cmd.json 都不读），启动路径干净；
* out.json 由定时器线程写，不在游戏线程的 hook 里写；
* 每条指令 id 去重，重复触发不会重放；
* 全部包在 try/catch 里，指令写错也伤不到引擎。

## 载荷格式

```json
{"id":"x","code":"return Process.getModuleByName('libgame.so').base"}
{"id":"x","op":"status"}          // 快照：uptime/fps/dvars/uiState/模块基址
{"id":"x","op":"threads"}         // 线程名与数量
{"id":"x","op":"fs","path":"...","depth":1}
{"id":"x","op":"fps"}             // eglSwapBuffers + vkQueuePresentKHR 计数
{"id":"x","op":"log","lines":8000}
{"id":"x","lua":"return tostring(1+1)"}   // 注入游戏 Lua，返回值回传
```

`code` 里可以直接用 `b`（libgame 模块基址）、`dir`、`MEDIA`、`log`、`Process`、`labFs`。
`labFs` 提供 `ls/stat/cat/put/cp/rm/mkdirp/mv/du`，读写私有目录全靠它。

## 工具

```bash
python work/lab_cmd.py status                 # 快照
python work/lab_cmd.py log --lines 4000       # 拉私有日志
python work/lua_send.py work/probe/xxx.lua 60 # 注入 Lua 并取回返回值
python work/send.py <id> work/tmp/xxx.js 40   # 任意 JS
python work/fps.py                            # 宿主机侧帧率（备用）
```

## 已经查清的事实（v16 实测）

* **CDN 包清单共 21 个**：type4（地图）只有 1 个 = `mp_mgl_verdansk`（2.22 GB，status 0 未安装）；
  type3 是 20 个语言包（index 14 的那个已装，status 5）；type5 是 0 号占位。
  ⇒ 服务器没有下发"装卸货场 / 酒店"这类图的包，包里也没有对应 shard，
    仅靠本版本资源**无法新增这两张图**；唯一能靠 CDN 补的是佛丹斯克（需 2.2 GB）。
* 包内实际可玩的 zone 只有：hardhat / rust / slaughterhouse / crash2 / escape4（+ 它们的子 zone）。
* `MatchRules` 的 setMode 对任意字符串都不报错（不校验），所以模式不能靠它验证，必须真开局。
* 脚本内 `globalThis.lab310CreateMatch` 已被 v14 删除，但 Lua 仍会返回
  `local-create-match-lobby:`，JS 侧会抛 ReferenceError（被 catch 住，无实际影响，v16 记录在案）。

## 启动卡死的观察（2026-11-24）

* 安装后第一次冷启动约 8 分钟才进菜单；之后正常启动约 30~60 s。
* 观察到的一种状态：Lua UI 已经是 `menu=MainMenuMobile;open=true;scene=true`，
  但 **0 帧输出**（eglSwapBuffers / vkQueuePresentKHR 全程 0，SurfaceFlinger 也没有该层的帧），
  进程内还挂着 in-process WebView（Chrome_* 线程），引擎主线程 `WZM_Main` 停在 futex_wait，
  CDN worker 全部空闲。
  ⇒ 引擎逻辑已加载，但渲染/首帧握手没完成，画面停在启动页。
* 处理：备份并清掉 `shard_cache/staging`、`shard_cache/*.bak`（备份在 media/cdnbak/）后重启。
* 教训：**"bridgeNext != 0" 不等于进菜单**（Lua UI 会在后台先起来），
  判断"真的可玩"必须同时看帧输出。
