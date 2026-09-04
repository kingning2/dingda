# python

桌面壳里的 **Python Server 子进程**（`uv run python -m src`）。不是 `server/src` 业务代码。

`lib.rs` setup 里 `PythonLifecycle::start_background`；关窗/`tray-quit` 调 `stop`。

## 本目录文件

### `mod.rs`

导出 `PythonConfig`、`PythonLifecycle`。

### `lifecycle.rs`

- `PythonConfig::from_env` — `DINGDA_HOST` / `DINGDA_PORT`，`server_dir` 来自 `paths::resolve_server_dir`
- `start_background` — spawn 子进程 → 轮询 `GET {api}/health`（最多约 30s）→ emit `server-ready` 或 `server-error`
- `is_ready` / `api_base_url` — 给 `commands/api.rs`
- `stop` — 杀进程树（Windows 额外收子进程）

探活失败不要在这里重试产品业务；前端听事件或轮询 `get_server_status`。

## 子目录

无。
