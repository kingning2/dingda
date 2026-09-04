# commands

前端 `invoke` 的 Tauri command。只做壳能力：Python 地址、本机对话框、CLI Agent 起停。  
账号/搜品/闲鱼不要加 command，走 `get_api_base_url` 之后 HTTP。

新增 command：本目录加函数，并在 [../lib.rs](../lib.rs) 的 `generate_handler!` 登记。

## 本目录文件

### `mod.rs`

`pub mod` 列出本层五个模块。无逻辑。

### `api.rs`

给 WebView 找 Python：

- `get_api_base_url` — `http://127.0.0.1:8787` 一类，来自 `PythonLifecycle`
- `get_server_status` — `{ ready, apiBaseUrl }`，`ready` 表示 `/health` 已通

前端不要写死端口（除非纯浏览器 dev）。

### `agent_runtime.rs`

外部 CLI Agent IPC：

- `list_agent_runtimes_command` → `agent::catalog::list_agent_runtimes`
- `probe_agent_runtime` / `login_agent_runtime` → `agent::probe`
- `launch_agent_runtime` — 拼 invocation，后台 `RuntimeManager::launch_with_app`，事件 `agent-event`
- `cancel_agent_runtime` — 按 `run_id` 杀进程

真正 spawn 在 [../runtime/README.md](../runtime/README.md)，这里只做参数校验和 spawn 任务。

### `dialog.rs`

系统文件选择：`pick_file` / `pick_folder`（blocking dialog 丢到 `spawn_blocking`）。返回路径或 `None`（用户取消）。

### `os.rs`

`show_in_folder`：资源管理器/Finder 定位文件（`tauri_plugin_opener`）。

### `frontend.rs`

`log_frontend_error`：把 React 错误打到壳 stderr（带北京时间、堆栈）。不是崩溃上报服务。

## 子目录

无。
