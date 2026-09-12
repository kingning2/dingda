# packages-rs

Tauri 壳拆出来的 Rust 成员包。工作区根清单在仓库根 [`Cargo.toml`](../Cargo.toml)，
成员 = `packages-rs/client` + `packages-rs/*`。

**一个包 = 一项可独立剥离的能力。** 删掉某个包目录 + 根清单里一行，对应能力即整体消失。

```text
common ← camoufox ← python ← client
common ← runtime  ← agent  ← client
```

依赖单向、无环。`common` 是唯一被所有包依赖的底座；`client` 是唯一可执行体。

## 成员包

| 包 | 职责 | 删掉它等于 |
|----|------|-----------|
| [common/](common/README.md) | 日志出口、路径解析、平台标签 | 壳无法工作（底座） |
| [camoufox/](camoufox/README.md) | Camoufox 定位与解压 | 去掉 Camoufox 浏览器支持 |
| [python/](python/README.md) | Python Server 子进程生命周期与启动环境 | 去掉内置 Server 拉起 |
| [runtime/](runtime/README.md) | 外部 CLI Runtime 定义 / 探测 / 托管下载 | 去掉 CLI 探测与下载 |
| [agent/](agent/README.md) | CLI Agent 目录与探测（IPC DTO） | 去掉设置页 Agent 列表 |
| [client/](client/README.md) | Tauri 客户端：窗口 / 托盘 / IPC / 编排 | 无桌面程序（唯一可执行体） |

## 构建入口

工作区根在仓库根，编译产物在 `<repo>/target/`。

```bash
cargo check --workspace          # 全部成员包
cargo test  --workspace
pnpm tauri dev                   # 桌面开发（经 scripts/tauri.mjs 注入 TAURI_APP_PATH）
```

Tauri CLI 默认只认 `<cwd>/src-tauri`；本仓库把壳放在 `packages-rs/client`，
靠包装脚本设置 **`TAURI_APP_PATH`** 定位。**不要直接跑 `pnpm exec tauri`**。


## 拆包时踩过的坑（改结构前必读）

1. **`cfg(dev)` 不能跨包用。** 它由 `tauri_build::build()` 只在壳的 `build.rs` 里下发；
   成员包没有 build.rs，写 `cfg!(dev)` 会恒为 false。故 `common::paths` 提供
   `set_dev_mode()`，由壳在 `run()` 首行注入。
2. **`env!("CARGO_MANIFEST_DIR")` 会变。** 文件一搬出壳包，该宏就指向成员包目录。
   故 `common::paths` 提供 `set_app_root()`，同样由壳注入。
3. **`target/` 跟着工作区根走。** 工作区根在仓库根，故编译产物在 `../target/`，
   不在 `packages-rs/client/target/`。搬动 target 会让 `tauri` 系构建脚本里烘焙的绝对路径
   失效，需要 `cargo clean -p tauri -p tauri-plugin-*` 后重建。

## 命名

包名不带产品前缀（不要 `dingda-`）。目录名与包名一致。

新增成员包：建 `packages-rs/<name>/`（`Cargo.toml` + `src/lib.rs` + `README.md`）
→ 根 `Cargo.toml` 的 `members` 已用 `packages-rs/*` 通配，无需登记
→ 在本文件「成员包」表加一行。
