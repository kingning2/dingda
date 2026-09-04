# src-tauri/src

壳的 Rust 入口。产品 HTTP 不在这里；前端用 `get_api_base_url` 拿到 Python 地址后自己 `fetch`。

```text
lib.rs
  ├─ python/          拉起 uvicorn
  ├─ commands/        invoke 给 React
  ├─ agent/           列表/探测 IPC 形状（薄）
  └─ runtime/         发现二进制、spawn CLI、解析 stdout → AgentEvent
```

`agent/` 不是 Python 产品 Agent。产品 Agent 在 `server/src/agent/`。

## 本目录文件

### `lib.rs`

`run()`：Tauri Builder。setup 里 `PythonLifecycle::start_background`（探活 `/health`，emit `server-ready`/`server-error`）。登记全部 command。托盘「显示/退出」。关窗或 `RunEvent::Exit` 时 `stop()` Python。

改「启动时干什么、有哪些 IPC」先看这里。

### `main.rs`

Windows release 隐藏控制台；`v2_lib::run()`。几乎无逻辑。

### `paths.rs`

`resolve_server_dir()`：`DINGDA_SERVER_DIR` 或 `CARGO_MANIFEST_DIR/../server`。Python 起进程和 MCP `uv run --directory` 都用它。

### `platform.rs`

`desktop_platform_label()`（macos/windows/linux）和注入 `window.__DINGDA_PLATFORM__` 的脚本。给无边框标题栏布局。不是 OS 文件对话框。

## 子目录

- [commands/](commands/README.md) — 前端 `invoke` 的函数
- [python/](python/README.md) — 子进程起停 Server
- [agent/](agent/README.md) — CLI Agent 目录给设置页（薄适配）
- [runtime/](runtime/README.md) — 真正拉起 Codex/Claude 等
