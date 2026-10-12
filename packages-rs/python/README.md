# python

桌面壳里的 **Python Server 子进程**（bundled `uv` + 国内镜像；开发态回退系统 `uv`）。

`lib.rs` setup 里解析 `resources/runtime`、解压平台 Camoufox zip、再 `PythonLifecycle::start_background`。

**打包在 GitHub Actions**（`.github/workflows/desktop-release.yml`），不依赖本机：`prepare-desktop-runtime.mjs` 按 runner OS/arch 从 `daijro/camoufox` Releases 拉对应 zip。

## 本目录文件

### `lib.rs`

导出 `EventSink`、`PythonConfig`、`PythonLifecycle`、`PythonLifecycleError`。

### `lifecycle.rs`

- `PythonConfig` — host/port、`server_dir`、`uv_bin`、`extra_env`（国内镜像 / `DINGDA_*`）
- `EventSink` — 事件出口插座。生产侧 `impl EventSink for AppHandle`，测试侧换成记录器，
  这样 `cargo test -p python` 能断言事件序列，不必起 Tauri / WebView
- `start_background` — `uv sync --frozen` → spawn → 轮询 `/health` → emit `server-ready` / `server-error`
  - 每个终局发且只发一个终态事件；spawn 失败也发 `server-error`，否则前端永远停在 warming
- 打包态 `startup_timeout` 可到 600s（首次拉依赖）
- `supervise` — 常驻 watchdog：启动成功后每 15s 探活 `/health`，连续失败
  2 次（≈30s 不可用）判定崩溃，带退避（2s→4s→8s）自动重启最多 3 次；
  成功重发 `server-ready`（前端状态机原样接住），耗尽发 `server-error`
  终态并停手。只随 `stop()`（用户退出）结束
- `stop` — 置退出旗标（监督循环看到即收工，不抢在退出后再拉起）→
  杀进程树；无 child 时退化为按端口 taskkill
- `kill_child` / `kill_all` — 恢复路径只回收自己的子进程不做端口兑底
  （崩溃进程的端口由 OS 回收，兑底杀「监听者」反而可能误伤）；
  已退出的子进程只 wait 回收句柄不 taskkill（PID 可能被系统复用）
- `parse_netstat_listeners` — 解析 `netstat -ano`，按本地地址端口**全等**匹配
  （子串匹配会让 80 命中 8080，误杀无关进程）

## 测试

`cargo test -p python`：覆盖 `/health` 探活超时、spawn 失败的事件序列、
启动超时回滚、watchdog 瞬断恢复 / 重试耗尽终态 / stop 取消监督、netstat 解析。
全部不依赖真实 Python 子进程与 WebView。

启发式路径（首发拉依赖、`server-ready` 真机时序）由 `e2e/` 的桌面冒烟覆盖。

## 相关

- [`../paths.rs`](../paths.rs) — server 工作副本、uv、镜像 env
- [`../camoufox.rs`](../camoufox.rs) — 按平台选 zip，用 `zip` crate 解压
