# src-tauri

叮答桌面壳（crate 名 `v2` / lib `v2_lib`）。职责：**窗口、托盘、起停 Python Server、OS 对话框、本机 CLI Agent**。  
账号、搜品、闲鱼 mtop 走 `server/` 的 HTTP，不要做成 Tauri command。

Rust 源码地图：[src/README.md](src/README.md)（每个模块一层 README）。

## 本目录文件

### `Cargo.toml`

依赖与 crate 类型（`staticlib`/`cdylib`/`rlib`）。Tauri 2、dialog、opener、tokio、reqwest。不要在这里加产品 SQLite。

### `Cargo.lock`

依赖锁定，不要手改。

### `build.rs`

`tauri_build::build()`。打包前生成绑定。

### `tauri.conf.json`

产品名、窗口（无边框 1280×800）、devUrl `1420`、CSP（允许连本机 Python `127.0.0.1`）、图标路径。改窗口尺寸/CSP 看这里。

### `.gitignore`

忽略 `target/` 等。

## 子目录

- [src/](src/README.md) — 全部 Rust 业务
- `capabilities/` — Tauri 权限（主窗 `default.json`：dialog/opener/窗口拖动）
- `icons/` — 打包图标，无逻辑
- `gen/` — 构建生成，不要手改

新增 IPC：加在 `src/commands/`，并在 `src/lib.rs` 的 `generate_handler!` 登记。
