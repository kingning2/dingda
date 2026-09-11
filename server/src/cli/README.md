# cli

外部 CLI Agent Runtime：在 Python Server 内启动 Codex / Claude / OpenCode / WorkBuddy，
按 **skill** 暴露 dingda 工具，流式产出事件。

前端经 `/v1/agent/runtimes/...` SSE 调用；**不再**由 Tauri `launch_agent_runtime` spawn。
产品侧的进程内 Agent（LLM + Tool 循环）在 [../agent/](../agent/README.md)，两者不要混用。

依赖方向：`api / tools / crawler → cli`。

## 本目录文件

### `base.py`

`CliRuntime`（插座）：一次会话的生命周期 —— 解析可执行文件 → 注入 → 拼 prompt → spawn →
流式解析 → 会话日志。插头只填 `id` / `name` / `binary` / `mcp_mode` / `stream_format` 并实现 `build_args`。

`run(..., role=...)` 按**角色**取三条策略（提示词怎么拼 / 注入给不给 / cwd 落哪），
不在本文件写「是不是子 agent」—— 差异全在 [roles/](roles/README.md)。

**注入方式当前统一为 skill**（`mcp_mode="none"`）：工具由 [../tools/skill.py](../tools/skill.py)
渲染成 `dingda-crawl/SKILL.md` 装到各 runtime 的 skills 目录。`inject/mcp.py`
（`codex-mcp` / `claude-mcp-json` / `opencode-env-content`）保留为历史分支，主链路已不走。

`compress_payload(payload, label)`：压要送进 CLI 的大 JSON 载荷（目前是修复 prompt 的
`dom_tree`）。`DINGDA_HEADROOM=0` 或未装 headroom-ai 时透传。

`cancel_run(run_id)` 也在本文件（进程表）。

### `registry.py`

`get_runtime(id)` 取插头（未知抛 `KeyError`）；`list_runtime_ids()`；`resolve_binary(runtime)` 按
`preferred → DINGDA_*_PATH → 托管目录 → PATH（含 Windows 注册表 PATH）→ 已知安装目录` 找可执行文件。

### `spawn.py`

`run_cli` / `cancel_run`：给调用方的稳定入口，按 id 取插头再起会话。生命周期不在本文件。

### `prompts.py` / `system.md`

选品系统前言；`compose_agent_prompt` 拼进 CLI stdin。首轮带前言；有 `session_id` 续聊时只传用户原文。
前言要求多轮 search、单次 limit 尽量大、累计约 ≥100 条样本。

### `steps.py`

把 toolCall / toolResult / live frame 收成前端 step / page；**kind 由后端决定**。

### `__init__.py`

包标记。

## 子目录

- [roles/](roles/README.md) — 会话角色（父 / 子 agent）
- [runtimes/](runtimes/README.md) — 各 CLI 插头
- [stream/](stream/README.md) — stdout → AgentEvent
- [inject/](inject/README.md) — MCP 注入（历史分支，当前用 skill）
- [live/](live/README.md) — 直播帧总线
- [repair/](repair/README.md) — DOM 修复子 agent
