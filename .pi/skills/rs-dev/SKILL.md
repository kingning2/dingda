---
name: rs-dev
description: 叮答 Rust 端（packages-rs/，Cargo workspace）编码规范。写或改 packages-rs/ 下 Rust 时使用：common/camoufox/python/client 四包各自收什么、Tauri 命令映射表、示例形状、三条路径陷阱与验证命令。
---

# Rust 编码规范（packages-rs）

## 1. 语言通用（写任何包之前）

1. **文件头**：`//!` 一行职责；`pub` 与关键私有函数 `///` 写「解决什么问题」，不复述签名。
2. **命名**：文件 snake_case；类型 PascalCase；函数/变量 snake_case；常量 UPPER_SNAKE。
   文件名不重复目录语义（`lifecycle.rs` 不是 `python_lifecycle.rs`）。
3. **错误**：包内可恢复错误用 `thiserror` 枚举 + `Result`；Tauri command 边界转
   `Result<T, String>`。业务路径**禁 `unwrap()` / `expect()`**；编译期可知的字面量可用
   `expect("静态值")`。
4. **日志**：`log::info!` / common 日志出口；生命周期三段 start → 关键步 → done|failed，
   字段 `key=value`。范本：`packages-rs/python/src/lifecycle.rs`。
5. **async**：不阻塞运行时——blocking 调用进 `spawn_blocking`；禁 `block_on` 嵌套。
6. **格式**：交码前 `cargo fmt`，不手调空格换行。

✓ 示例（`packages-rs/python/src/lifecycle.rs` 形状）：

```rust
//! Python Server 子进程生命周期。
/// 启动内嵌 FastAPI 进程，等待健康检查通过后置为 Running。
/// 负责失败时的日志与退出码回收，不负责 HTTP 转发（那是前端的事）。
pub async fn start(&self) -> Result<(), LifecycleError> {
    log::info!(target: "rs.python", "server.start root={}", self.app_root.display());
    ...
    log::info!(target: "rs.python", "server.done");
    Ok(())
}
```

✗ 反例：

```rust
let cfg = configs.get(0).unwrap();          // 业务路径禁 unwrap
log::info!("done");                          // 缺字段与 start 段，生命周期不完整
```

## 2. 三条路径陷阱（packages-rs/README.md 实证，新代码必防）

| 陷阱 | 正确做法 |
|------|----------|
| `#[cfg(dev)]` 分支生产忘切 | 用 common 注入的运行模式开关，不散写 cfg |
| `env!("CARGO_MANIFEST_DIR")` 指向包目录而非运行目录 | 路径一律经 `common::paths` 解析（dev 模式指向 `<repo>/`，打包模式指向安装根） |
| 硬编码 `target/` 或相对路径找产物 | 同上，经 common；产物实际在 `<repo>/target/`（工作区根） |

## 3. 各包收什么（写错包 = 架构违规）

依赖方向唯一合法：`common ← camoufox ← python ← client`（上层 README 只引用下层）。

| 包 | 收什么 | 禁止 |
|----|--------|------|
| `common/` | 日志出口、路径解析、平台标签——唯一底座 | 出现业务语义、依赖其他三包 |
| `camoufox/` | Camoufox 定位与解压 | 被 client 之外越层引用；碰 HTTP 业务 |
| `python/` | Python Server 子进程生命周期（start/stop/健康检查） | 探测 camoufox 目录（经 common）；碰前端事件 |
| `client/` | Tauri 壳：窗口/托盘/IPC/OS 能力 | 实现 HTTP 业务逻辑；直接 fs 探测其他包内部结构 |

```
packages-rs/
├── common/src/       # paths.rs logging.rs platform.rs
├── camoufox/src/     # lib.rs camoufox.rs
├── python/src/       # lifecycle.rs
└── client/src/       # main.rs lib.rs commands/
```

### common（怎么被消费）

✓ 路径解析（实证 `common/src/paths.rs`）——两个基准目录由壳启动时注入，包内不自己算：

```rust
//! 设计说明（原文）：不能自己算：本文件在 packages-rs/common，
//! env!("CARGO_MANIFEST_DIR") 只会指向本包目录。
pub fn set_app_root(root: PathBuf);   // 壳包目录 packages-rs/client，resources/runtime 用
pub fn set_repo_root(root: PathBuf);  // 仓库根，uv workspace 根用它
```

- 注意：`find_camoufox_exe` 这类专属知识不在 common（实证：已迁去 camoufox 包
  以打断 paths ↔ camoufox 循环依赖）。

### camoufox（怎么被消费）

✓ 实证 `lib.rs` 头注：从打包 resources 的 zip 解压到 `~/.dingda/v2/camoufox/current`，
对外只出这几个函数，壳把结果注入 `DINGDA_CAMOUFOX_EXE` 给 Python：

```rust
pub use camoufox::{
    bundled_camoufox_zip, camoufox_platform_tag, ensure_camoufox_exe,
    extract_camoufox_zip, find_camoufox_exe,
};   // 只做定位与解压，不启动浏览器
```

### python（怎么被消费）

✓ 实证 `lifecycle.rs` 公开面——壳只调这几个方法，不直接碰进程细节：

```rust
PythonLifecycle::from_env()                     // 读环境装配配置
lifecycle.start_background(...).await            // 起 Server，后台等健康检查
lifecycle.is_ready() / lifecycle.api_base_url() // 探活与地址（get_server_status 用）
lifecycle.stop().await / lifecycle.supervise(...) // 停止与守护
```

- 注意：HTTP 转发不在这（前端直联 Server）；本包只管进程生死。

## 4. client/ 命令映射表（新增交互照此登记）

新增命令 = `commands/<域>.rs` 写 `#[tauri::command]` + `commands/mod.rs` 一行
+ `lib.rs` 的 `generate_handler!` 一行。**一个文件只服务一个域**。

| 文件 | command | 前端 invoke 名 | 语义 |
|------|---------|----------------|------|
| `commands/api.rs` | `get_api_base_url` | `get_api_base_url` | 取内嵌 Server 地址 |
| `commands/api.rs` | `get_server_status` | `get_server_status` | Server 探活状态 |
| `commands/dialog.rs` | `pick_file` | `pick_file` | 系统文件选择框（取消返回 None） |
| `commands/dialog.rs` | `pick_folder` | `pick_folder` | 目录选择框 |
| `commands/frontend.rs` | `log_frontend_error` | `log_frontend_error` | 前端错误回传壳日志 |
| `commands/os.rs` | `show_in_folder` | `show_in_folder` | 资源管理器定位文件 |

```rust
// commands/dialog.rs —— 一个 command 只做：参数 → 调成员包/系统能力 → 返回
#[tauri::command]
pub async fn pick_file(app: AppHandle) -> Result<Option<String>, String> {
    // 职责单一：弹对话框，不做业务过滤
    ...
}
```

- 注意：command 里出现「调 Server 接口并组装产品数据」即违规——产品业务归前端或 Python；
  壳只做 OS 能力与进程编排（AGENTS.md 2.1 第 8 条：禁止为架构新增 Rust Crawler/Browser/DB）。

## 5. 验证要求（交码前必跑）

```bash
cargo check --workspace --all-targets
cargo fmt
```

- 要真跑壳验证：**必须 `pnpm tauri dev`**（`scripts/tauri.mjs` 注入 `TAURI_APP_PATH`）；
  **禁止直接 `pnpm exec tauri`**（AGENTS.md 1.4 / 7）。
