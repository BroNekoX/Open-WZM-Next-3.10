# WZM 3.10 下载子系统（CDNI）逆向笔记

`libgame.so` 里是一套完整的 CDN 安装器：清单（manifest）+ 分片（shard）+ HTTP Range 断点续传 + 多线程 worker。
下面是可用的落点，配合 `work/analysis/libgame_310.symbols` 在 IDA 里直接跳。

---

## 1. 端点与路径模板（全部是明文，vaddr 已定位）

| vaddr | 字符串 | 用途 |
|---|---|---|
| `0x4e45b8` | `https://prod.cdni.callofduty.com/wzm/shard_cdn/android/_manifest/cdni.meta` | **正式清单入口** |
| `0x536c2f` | `/shard_cdn/%s/%s/cdni_manifest_%d.manifest.%lx` | 按版本取清单 |
| `0x4ac555` | `/shard_cdn/%s/%c%c/%s.shard` | 分片下载（按前 2 字符分桶） |
| `0x4f5eeb` | `/shard_cdn/%s/_aggregate/%s.%lx` | 聚合包 |
| `0x4beccc` | `/shard_cdn/%s/%s/environment.config` | 环境配置 |
| `0x4b34f4` | `https://dev.cdni.callofduty.com/wzm/manifest` | **测试服入口** |
| `0x4b87be` | `CDNI_UseDevServer` | 切测试服的开关名 |
| `0x4ac353` | `isCDNIFinished` | 启动页轮询的就是它 |
| `0x4d0f03` | `passPreloginFence` | 登录前置栅栏 |
| `0x4a63c1` | `CDNI_DOWNLOAD_SHARD_REGISTER_ERROR` | 分片注册失败 |
| `0x4d0e9d` | `CDN-Install-Worker0` | 下载线程名 |

其它相关：`[CDN Install] Manifest larger than CDNI_MAX_MANIFEST_SIZE`、`ManifestOk`、`RequestManifest`、`FetchingPreloadManifest`、`cdni.pid`、`manifest.dat`、`shard/manifest.json`、`Content-Range: bytes …`、`HTTP server doesn't seem to support byte ranges. Cannot resume.`

## 2. 下载模型（从字符串与调用关系推断）

```
启动
 └ 取 cdni.meta（含当前版本号）
    └ 取 cdni_manifest_<ver>.<hash>  → 解析出「文件名 → shard 路径 + 大小 + 校验」
       └ 按 /shard_cdn/<ver>/<xx>/<name>.shard 下载，支持 Range 续传
          └ 落盘后注册进 file DB（CDNI_DOWNLOAD_SHARD_REGISTER_ERROR 在失败时打）
             └ 全部完成 → isCDNIFinished = true → 启动页关 WebView
```

它是**按路径拉取**的，不是按 id 查询——也就是说，只要能让它把 `prod.cdni.callofduty.com` 解析到本地，并且本地有同名路径的文件，整套流程就能在完全离线的情况下跑通。

## 3. "指到本地"的三条路（按可行性）

### 方案 A：劫持 `getaddrinfo` + 放行 TLS 校验（推荐先试）
- 现有注入脚本已经 hook 了 libc 的 `open/read/close`，加一个 `getaddrinfo`/`connect` 的 hook 很自然；
- 把 `prod.cdni.callofduty.com` 改成 `127.0.0.1`，本地起一个 HTTPS 服务；
- **难点**：证书校验。需要同时 hook curl 的 `CURLOPT_SSL_VERIFYPEER`（`curl_easy_setopt` 参数）或直接 hook 校验回调返回成功；
- 优点：不改引擎、不动包体资源，外壳可以随时换内容。

### 方案 B：改 URL 构造处的字符串
- 在 `0x4e45b8` 附近找引用它的函数（IDA 里对它做 xref），把 host 换成可控的本地地址；
- 缺点：字符串是常量池里的，改长度受限；且可能有多处构造。

### 方案 C：利用 `CDNI_UseDevServer`
- 如果有 dvar/开关能在运行时切到 `dev.cdni.callofduty.com`，可以把它指向一个我们已经能控制的域名（需要 DNS/hosts，非 root 不可行）；
- 实际上更适合做"测试服"而不是本地化，除非你能改 hosts。

> 结论：**方案 A 是最干净的**——一次性把 CDNI 变成"本地文件服务器"，下载逻辑、校验、断点续传全部由引擎自己完成，稳定性和速度都比复制文件可靠。

## 4. "更好的下载逻辑"具体能改什么

| 目标 | 引擎侧可做的事 |
|---|---|
| 并行度 | `CDN-Install-Worker0` 说明是多线程 worker；worker 数量可能在初始化时写死，可 hook 改成 4–8 |
| 续传 | 已支持 Range；只要本地服务返回 `Accept-Ranges: bytes` 就能断点续传 |
| 完整性 | 清单里有每片大小/哈希，本地服务只要内容正确就不会触发重下 |
| 避免重下 | 清单版本号不变时不会重下；换版本才全量 |
| 失败重试 | `CDNI_DOWNLOAD_TASK_EXCEED_MAX_ATTEMPTS` 说明有重试上限，可在 hook 里放宽 |

## 5. 下一步

1. 在 IDA 里 xref `0x4e45b8`，找到 `RequestManifest` 的调用者，确认 manifest 解析后的结构（文件名、大小、哈希字段偏移）；
2. 写 `getaddrinfo` hook + 本地 HTTPS 服务（自签证书 + 放行校验），先只代理 `cdni.meta` 一个请求，验证能否被接受；
3. 通了之后把 3.39 GB 资源按同样路径摆好，就能完全脱离外网。

---

*说明：本节只涉及客户端下载协议的静态分析，不包含任何服务端实现。*