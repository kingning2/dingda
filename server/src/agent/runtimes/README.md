# agent/runtimes

在 **Python Server** 内启动外部 CLI Agent（Codex / Claude / OpenCode），注入 dingda-mcp，流式产出事件。

前端经 `/v1/agent/runtimes/...` SSE 调用；**不再**由 Tauri `launch_agent_runtime` spawn。

## 本目录文件

### `registry.py`

`RuntimeSpec` + `get_runtime` / `resolve_binary`。已实现：`codex`、`claude`、`opencode`。

### `mcp_inject.py`

`apply_mcp_inject`：claude 写 cwd `.mcp.json`；codex 加 `-c mcp_servers.goofish=...`；opencode 设 `OPENCODE_CONFIG_CONTENT`。

### `stream.py`

`parse_lines`：Codex JSON / Claude stream-json / OpenCode JSON → AgentEvent dict。

### `steps.py`

把 toolCall / toolResult / live frame 收成前端 step / page；**kind 由后端决定**。

### `live_hub.py`

按 run_id 收 MCP `preview` 投递的 browserFrame，spawn 侧 drain 进 SSE。

### `prompts.py` / `dingda-system.md`

选品系统前言；`compose_agent_prompt` 拼进 CLI stdin。首轮带前言；有 `session_id` 续聊时只传用户原文。前言要求多轮 search、单次 limit 尽量大、累计约 ≥100 条样本。

### `spawn.py`

`run_cli` / `cancel_run`：asyncio 子进程 + 内存 run 表。

### `__init__.py`

包标记。
