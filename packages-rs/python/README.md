# python

桌面壳里的 **Python Server 子进程**（bundled `uv` + 国内镜像；开发态回退系统 `uv`）。

`lib.rs` setup 里解析 `resources/runtime`、后台解压平台 Camoufox zip、再
`PythonLifecycle::start_background`。Camoufox 解压**不进 setup 主线程**（见下方 `env.rs`）。

**打包在 GitHub Actions**（`.github/workflows/desktop-release.yml`），不依赖本机：`prepare-desktop-runtime.mjs` 按 runner OS/arch 从 `daijro/camoufox` Releases 拉对应 zip。

## 本目录文件

### `lib.rs`

导出 `EventSink`、`PythonConfig`、`PythonLifecycle`、`PythonLifecycleError`、
`desktop_runtime_env`、`resolve_camoufox_env`。

### `env.rs`

- `desktop_runtime_env(app, server_dir)` — 快路径环境变量（镜像 / uv / venv），
  **不含** Camoufox 解压，可在 setup 主线程调用
- `resolve_camoufox_env(app)` — 必要时解压 zip，返回 `DINGDA_CAMOUFOX_EXE`；
  必须由壳丢进 `spawn_blocking`，否则首次解压会卡住窗口渲染

### `lifecycle.rs`

- `PythonConfig` — host/port、`server_dir`、`uv_bin`、`extra_env`（国内镜像 / `DINGDA_*`）
- `push_extra_env` — 启动前追加环境（Camoufox 后台解压完成后注入）
- `EventSink` — 事件出口插座。生产侧 `impl EventSink for AppHandle`，测试侧换成记录器，
  这样 `cargo test -p python` 能断言事件序列，不必起 Tauri / WebView
- `start_background` — `uv sync --frozen` → spawn → 轮询 `/health` → emit `server-ready` / `server-error`
  - 每个终局发且只发一个终态事件；spawn 失败也发 `server-error`，否则前端永远停在 warming
- 打包态 `startup_timeout` 可到 600s（首次拉依赖）
- `stop` — 杀进程树；无 child 时退化为按端口 taskkill
- `parse_netstat_listeners` — 解析 `netstat -ano`，按本地地址端口**全等**匹配
  （子串匹配会让 80 命中 8080，误杀无关进程）

## 测试

`cargo test -p python`：覆盖 `/health` 探活超时、spawn 失败的事件序列、
启动超时回滚、netstat 解析。全部不依赖真实 Python 子进程与 WebView。

启发式路径（首发拉依赖、`server-ready` 真机时序）由 `e2e/` 的桌面冒烟覆盖。

## 相关

- [`../paths.rs`](../paths.rs) — server 工作副本、uv、镜像 env
- [`../camoufox.rs`](../camoufox.rs) — 按平台选 zip，用 `zip` crate 解压
