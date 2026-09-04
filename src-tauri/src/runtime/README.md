# runtime

本机 CLI Agent 运行时：**找二进制 → 探测 → 拼参数 → spawn → 解析 stdout → `AgentEvent`**。

不负责安装 CLI。不跑闲鱼/账号业务。MCP 只在**这一次进程**里注入，不改 `~/.codex/config.toml`。

```text
RuntimeDefinition (defs/)
  → resolution → detection / model_discover
  → invocation (+ mcp/) → process::spawn
  → parsers → manager emit("agent-event")
```

禁止在 `manager.rs` 里 `if runtime_id == "codex"`。差异放 `defs/<id>.rs` 和对应 parser。

## 本目录文件

### `mod.rs`

子模块声明；对外 re-export：`RuntimeManager`、`find_runtime`、`resolve_executable`、`RuntimeDefinition`、`AgentEvent` 等。

### `types.rs`

插座与快照：`RuntimeDefinition`（id、binary、`build_args` 函数指针、`discover_models`、`stream_format`、`external_mcp_injection`）、`RuntimeInvocation`、`RuntimeDetection`、`ResolvedExecutable`、`StreamFormat`、`RuntimeModel`。新 CLI 先看字段再填 defs。

### `registry.rs`

`RUNTIME_REGISTRY` 静态表 + `find_runtime(id)`。新增 CLI：defs 里 `pub const` 后**必须**在这里加一行。

### `resolution.rs`

`resolve_executable`：`DINGDA_*_PATH` → 动态 PATH（含 Windows 注册表/shell 缓存）→ 已知安装目录。可选 `validate_executable`。Detection 和 Launch 共用，避免「设置页找到了、启动找不到」。

### `detection.rs`

`detect_runtime`：resolve 之后跑 `version_args`、按 capabilities 做 auth probe。给 probe 用。

### `invocation.rs`

`build_invocation` / `invocation_context`：definition + prompt/cwd/model → 可 spawn 的 `RuntimeInvocation`，再 `apply_external_mcp_injection`。`invocation_context` 会用 [`prompts/`](prompts/) 里的 Markdown 系统前言拼进 prompt。

### `prompts/`

`dingda-system.md`：叮答调研系统前言（MCP `search`/`product`）。`compose_agent_prompt` 在 Rust 统一拼接，前端只传用户原文。

### `process.rs`

`spawn_process`（stdin 可送 prompt）、`read_stdout_lines` 按行回调。stderr 尚未当 AgentEvent 解析。

### `runs.rs`

进程表：`register` / `cancel` / `unregister`。`cancel_agent_runtime` 走这里杀 `run_id`。

### `event.rs`

`AgentEvent`（`RunStarted` / `TextDelta` / `ToolCall` …）与 `AgentEventEnvelope`（带 `run_id`）。`StreamParser::feed`。前端只认这套，不认 Codex 原始 JSON。对齐 `src/contracts/agent-event.ts`。

### `manager.rs`

`RuntimeManager`：`launch_with_app` 编排全流程并 `emit("agent-event")`；`cancel_run`；`find`/`resolve` 转调 registry。Command 层调它，不要直接 `Command::new("codex")`。

## 子目录

- [defs/](defs/README.md) — 每个 CLI 一份 `RuntimeDefinition`
- [model_discover/](model_discover/README.md) — 模型列表 helper
- [mcp/](mcp/README.md) — 进程级注入 `dingda-mcp`
- [parsers/](parsers/README.md) — stdout → `AgentEvent`

与 [../agent/README.md](../agent/README.md) 的分工：那边是 IPC DTO，这边是进程。
