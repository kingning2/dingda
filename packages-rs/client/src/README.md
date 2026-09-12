# packages-rs/client/src

Tauri 壳本体。只做**编排**：组装 Builder、登记 IPC、起停 Python、托盘与窗口。
产品 HTTP 不在这里；前端用 `get_api_base_url` 拿到 Python 地址后自己 `fetch`。

具体能力已拆到仓库根的 [`packages-rs/`](../../packages-rs/README.md)：

```text
lib.rs / main.rs
  └─ commands/         invoke 给 React
        ├─ api.rs          → python   （Server 状态）
        ├─ agent_runtime.rs→ agent / runtime
        ├─ dialog.rs       纯 OS 对话框
        ├─ frontend.rs     → common   （日志）
        └─ os.rs           纯 OS 打开目录

packages-rs/
  ├─ common/      日志出口 + 路径解析 + 平台标签
  ├─ camoufox/    Camoufox 定位与解压
  ├─ python/      Python 子进程生命周期与启动环境
  ├─ runtime/     外部 CLI Runtime 定义 / 探测 / 下载
  ├─ agent/       CLI Agent 目录与探测（IPC DTO）
  └─ client/      ← 本包（唯一可执行体）
```

依赖方向（单向，无环）：`common ← camoufox ← python ← client`、`common ← runtime ← agent ← client`。

## 本目录文件

### `lib.rs`

`run()`：Tauri Builder。**开头必须先注入三个开关**：`paths::set_app_root()`、
`paths::set_repo_root()`、`paths::set_dev_mode()`。三者都早于任何 `resolve_*` /
`is_packaged_install()`，原因见 [../../common/README.md](../../common/README.md)。

- `set_app_root` — 壳包目录（`packages-rs/client`），`resources/runtime` 的基准
- `set_repo_root` — 仓库根（其上两级），`server/` 的基准
- `set_dev_mode` — `cfg(dev)` 由 `build.rs` 的 `tauri_build::build()` 只对本包下发，
  `common` 拿不到；不注入会把 dev 误判成安装包

「仓库根 = 壳包目录的上两级」由 `repo_root_from_manifest_dir()` 承担。这段推导没有
类型保护：壳一旦被挪到更深一层（如 `packages-rs/<scope>/client`），
`resolve_server_dir()` 会**静默**指向不存在的目录，直到 Python 启动失败才暴露。
故文件末尾 `mod tests` 有两条回归测试兜底（`cargo test -p client`）：
推导结果下必须真实存在 `pyproject.toml` + `packages-py/` 与 `packages-rs/`；层级不足时退化为原路径。

setup 里 `PythonLifecycle::start_background`（探活 `/health`，emit `server-ready`/`server-error`）。
登记全部 command。托盘「显示/退出」。关窗或 `RunEvent::Exit` 时 `stop()` Python。

改「启动时干什么、有哪些 IPC」先看这里。

### `main.rs`

Windows release 隐藏控制台；`client::run()`。几乎无逻辑。

## 子目录

- [commands/](commands/README.md) — 前端 `invoke` 的函数

## 不在本目录的（已拆包）

| 原来在这里 | 现在在 |
|-----------|--------|
| `logging.rs`、`paths.rs`、`platform.rs` | `packages-rs/common/` |
| `camoufox.rs` | `packages-rs/camoufox/` |
| `python/` | `packages-rs/python/` |
| `runtime/` | `packages-rs/runtime/` |
| `agent/` | `packages-rs/agent/` |

新增能力优先加到对应成员包，不要在壳里再堆模块。
