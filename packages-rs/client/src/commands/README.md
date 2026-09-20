# commands

前端 `invoke` 的 Tauri command。只做壳能力：Python 地址、本机对话框、OS 集成。  
Agent 运行、账号、搜品一律走 HTTP（Python Server），不经壳。

新增 command：本目录加函数，并在 [../lib.rs](../lib.rs) 的 `generate_handler!` 登记。

## 本目录文件

### `mod.rs`

`pub mod` 列出本层四个模块。无逻辑。

### `api.rs`

给 WebView 找 Python：

- `get_api_base_url` — `http://127.0.0.1:8787` 一类，来自 `PythonLifecycle`
- `get_server_status` — `{ ready, apiBaseUrl }`，`ready` 表示 `/health` 已通

前端不要写死端口（除非纯浏览器 dev）。

### `dialog.rs`

系统文件选择：`pick_file` / `pick_folder`（blocking dialog 丢到 `spawn_blocking`）。返回路径或 `None`（用户取消）。

### `os.rs`

`show_in_folder`：资源管理器/Finder 定位文件（`tauri_plugin_opener`）。

### `frontend.rs`

`log_frontend_error`：把 React 错误打到壳 stderr（带北京时间、堆栈）。不是崩溃上报服务。

## 子目录

无。
