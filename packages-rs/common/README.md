# common

壳的共享基础层。**不含任何产品业务能力**，被 camoufox / python / runtime / agent 与壳共同依赖。

改日志格式、路径规则、平台判定都在这里改。

## 本目录文件

### `logging.rs`

壳内唯一日志出口：`logging::log(Scope::{Agent,Shell,Frontend,Runtime}, message, detail)`
打到 stderr，格式 `[scope] 北京时间 message detail`，scope 决定前缀颜色
（agent 绿 / shell 青 / frontend 品红 / runtime 黄）。新增日志不要再自己 `eprintln!`。

### `paths.rs`

「壳需要的目录在哪」的一组纯路径函数，不启动进程、不碰 Camoufox。

- `data_dir()` — `~/.dingda/v2`（与 Python `data_dir()` 对齐）
- `resolve_server_dir()` — 开发态仓库 `server/`，`DINGDA_SERVER_DIR` 可覆盖
- `resolve_resource_dir(app)` / `resolve_runtime_dir(app)` — 安装包 resources / `resources/runtime`
- `resolve_uv_bin(app)` — 打包态优先 resource 里的 uv，开发态用 PATH
- `ensure_server_workdir(app)` — 可写 Server 工作副本（打包态从 resources 同步）
- `is_packaged_install()` — 是否客户安装包（非 `tauri dev`）

**两个必须由壳注入的开关**（见文件头注释）：

| 函数 | 为什么不能自己算 |
|------|------------------|
| `set_app_root()` | `env!("CARGO_MANIFEST_DIR")` 在本包会指向 `packages-rs/common`，不是 `packages-rs/client` |
| `set_dev_mode()` | `cfg(dev)` 由 `tauri_build::build()` 只在壳的 build.rs 下发，本包拿不到 |

壳在 `packages-rs/client/src/lib.rs` 的 `run()` 首两行调用它们，必须早于任何 `resolve_*`。

### `platform.rs`

`desktop_platform_label()`（macos/windows/linux）与注入 `window.__DINGDA_PLATFORM__`
的脚本。给无边框标题栏布局用。**不是** OS 文件对话框（那个在壳的 `commands/dialog.rs`）。

## 子目录

无。

## 边界

本包只放「与产品无关、被多层复用」的东西。一旦某个函数只服务一个能力
（如 Camoufox 的 exe 名、Python 的镜像地址），就应移到对应包——这正是
`find_camoufox_exe` 与 `desktop_runtime_env` 迁出的原因。
