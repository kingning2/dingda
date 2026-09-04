# runtime/defs

每个文件一个 CLI 插头：导出 `pub const FOO: RuntimeDefinition`。  
`build_args` 函数指针指向 `build_args.rs`；`discover_models` 组合 [../model_discover/README.md](../model_discover/README.md)。

新增：本目录加 `<id>.rs` → `mod.rs` `pub use` → [../registry.rs](../registry.rs) 登记。不要在业务里 match id。

`external_mcp_injection` 有的 CLI 已声明（如 `claude-mcp-json`），见 [../mcp/README.md](../mcp/README.md)。已实现：Codex / OpenCode / MiMo / Claude / CodeBuddy / Cursor / Qwen / Qoder / Grok / DeepSeek / Pi / Trae；`deepseek-harness` 故意不注入；未知 mode 打日志后跳过。

## 本目录文件

### `mod.rs`

`mod` + `pub use` 所有常量。registry 从这里 import，不要从单个文件散引。

### `build_args.rs`

各 CLI 启动参数（对齐 open-design）：

- Codex：`exec --json` + sandbox / `-C` / `--add-dir`；续聊 `exec resume … <thread_id>`
- Claude：stream-json + `--permission-mode bypassPermissions` + `--add-dir` / `--resume`
- OpenCode：`run --format json` + `--dangerously-skip-permissions` + `--dir` + `-s` / `-m`
- Cursor / ACP / DSH / plain_exec 等

defs 只填函数指针。

### `validate.rs`

`validate_dsh_executable`：DeepSeek Harness `--probe` 必须回 dsh JSON。挂在 `DEEPSEEK_HARNESS.validate_executable`，避免 PATH 上撞名。

`validate_cursor_executable` / `looks_like_cursor_agent`：Cursor 的备用名 `agent` 会与 Grok 的 `agent.exe` 撞名；拒绝 `.grok` 路径与 `grok` 版本串，仅接受 `cursor-agent` 或带 cursor / `.local/bin` 信号的 `agent`。

### `codex.rs`

`CODEX`，id `codex`。`external_mcp_injection: Some("codex-mcp")`。模型：`login status` 成功则 `debug models`，否则静态列表。

### `claude.rs`

`CLAUDE`，id `claude`。stream-json。注入标记 `claude-mcp-json`（cwd `.mcp.json`）。

### `opencode.rs`

`OPENCODE`，id `opencode`。注入 `opencode-env-content`。

### `cursor.rs`

`CURSOR`，id `cursor-agent`。注入 `cursor-mcp-json`（`.cursor/mcp.json`）。带 `validate_cursor_executable`，避免把 Grok 的 `agent` 当成 Cursor。

### `mimo.rs`

`MIMO`，id `mimo`。注入 `mimo-env-content`；`build_args` 复用 OpenCode（`run --format json`）。

### `deepseek.rs`

`DEEPSEEK`，id `deepseek`（CodeWhale）。注入 `deepseek-mcp-config`（`.dingda/mcp.json` + env）。

### `deepseek_harness.rs`

`DEEPSEEK_HARNESS`，id `deepseek-harness`，二进制 `dsh`。**不**注入 MCP（YAML 插件体系）。

### `qwen.rs`

`QWEN`，id `qwen`。注入 `qwen-settings-json`（`.qwen/settings.json`）。

### `qoder.rs`

`QODER`，id `qoder`。注入 `claude-mcp-json`（项目 `.mcp.json`）。

### `grok.rs`

`GROK`，id `grok-build`。注入 `claude-mcp-json`（Grok 兼容读 `.mcp.json`）。

### `pi.rs`

`PI`，id `pi`。注入 `pi-mcp-json`（`.pi/mcp.json`）。

### `trae.rs`

`TRAE`，id `trae-cli`。注入 `acp-merge`（spawn 时 ACP 握手 + mcpServers）。

### `codebuddy.rs`

`CODEBUDDY`，id `codebuddy`。注入标记 `claude-mcp-json`（与 Claude 同实现）。

## 子目录

无。
