# packages-rs/client

Tauri 客户端（crate 名 `client`）。职责：**窗口、托盘、起停 Python Server、OS 对话框、本机 CLI Agent 编排**。
账号、搜品、闲鱼 mtop 走 `server/` 的 HTTP，不要做成 Tauri command。

Rust 源码地图：[src/README.md](src/README.md)。

## 与 Tauri CLI 的约定（重要）

Tauri v2 默认只认 `<cwd>/src-tauri`。本包在 `packages-rs/client`，故：

- `package.json` 的 `tauri` 脚本指向 `scripts/tauri.mjs`
- 该包装脚本设置 **`TAURI_APP_PATH=packages-rs/client`**，CLI 据此定位本包
- 因此**不要直接跑 `pnpm tauri`**（走的是包装脚本），也不要把本包改回 `src-tauri`

`tauri.conf.json` 里所有相对路径都以**本包目录**为基准：
`frontendDist: "../../dist"`、`resources/runtime/**/*`。

## 本目录文件

### `Cargo.toml`

包名 `client` / lib `client`，crate 类型 `staticlib`+`cdylib`+`rlib`。
只依赖 `packages-rs/` 的成员包 + Tauri 系 + serde，**不直接依赖** tokio / reqwest / zip / chrono（那些在成员包里）。
不要在这里加产品 SQLite。

### `build.rs`

`tauri_build::build()`。打包前生成绑定。

**注意**：`cfg(dev)` 由它下发，且**只对本包生效**。成员包拿不到该 cfg，
所以 `common::paths::set_dev_mode()` 必须由 `src/lib.rs` 显式注入。

### `tauri.conf.json`

产品名、窗口（无边框 1280×800）、devUrl `1420`、CSP（允许连本机 Python `127.0.0.1`）、图标路径。
`beforeDevCommand` 跑 `pnpm dev`；`beforeBuildCommand` 跑 `pnpm prepare:desktop-runtime && pnpm build`，
两者都在**前端目录（仓库根）**执行。OCR 不在启动/构建时预热，首次识图再懒加载。

## 子目录

- [src/](src/README.md) — 壳本体（lib.rs / main.rs / commands）
- `capabilities/` — Tauri 权限（主窗 `default.json`：dialog/opener/窗口拖动）
- `icons/` — 打包图标，无逻辑
- `gen/` — 构建生成，不要手改
- `resources/` — 打包资源；`resources/runtime/` 由 `scripts/prepare-desktop-runtime.mjs` 生成，不入库

新增 IPC：加在 `src/commands/`，并在 `src/lib.rs` 的 `generate_handler!` 登记。
新增能力：优先加到 `packages-rs/` 下对应成员包，不要在壳里再堆模块。
