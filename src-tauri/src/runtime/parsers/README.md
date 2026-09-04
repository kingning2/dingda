# runtime/parsers

把 CLI **一行 stdout** 变成 `AgentEvent`。`manager` 用 `create_parser(stream_format, runtime_id, run_id)` 取实现。

前端不解析 Codex/Claude 原始帧，只听 `agent-event`。

## 本目录文件

### `mod.rs`

`create_parser` 工厂：

- `ClaudeStreamJson` / Copilot / Qoder → `ClaudeStreamParser`
- `JsonEventStream` + `codex`/`cursor-agent`/`mimo` → `CodexStreamParser`
- 同上 + `opencode` 等 → `OpenCodeStreamParser`
- ACP / Pi / DSH → `JsonEventStreamParser`
- `Plain` → `PlainStreamParser`

`parse_json_line`：空行忽略、非法 JSON 丢弃。

### `codex.rs`

`CodexStreamParser`：`response.output_text.delta`、tool 等 → `TextDelta`/`ToolCall`。Cursor / Mimo 共用。

### `claude.rs`

`ClaudeStreamParser`：`content_block_delta`、`tool_use`。CodeBuddy / Qoder 也走这里。

### `opencode.rs`

`OpenCodeStreamParser`：`text` / `part_delta` / `tool_use`。

### `json_event.rs`

`JsonEventStreamParser`：目前内部复用 Codex parser，给 ACP JSON-RPC 等「长得像 JSON 行」的流当 fallback。

### `plain.rs`

`PlainStreamParser`：非空行整段变 `TextDelta`。没有 JSON 的 CLI 用。

## 子目录

无。事件形状：[../event.rs](../event.rs) 与 `src/contracts/agent-event.ts`。
