# domains/runtime

Python Server 自己的进程快照（uptime、是否 running）。  
不是 Tauri 里 Codex/Claude 的 Agent Runtime，不要往这里塞 CLI 事件。

## 本目录文件

### `service.py`

`RuntimeService.snapshot()` → `{ok, state, uptime_ms, 可选 phase}`。`api/runtime.py` 与 `api/bootstrap.py` 使用。

### `__init__.py`

包标记。

## 子目录

无。
