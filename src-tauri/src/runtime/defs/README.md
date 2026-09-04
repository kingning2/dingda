# runtime/defs

每个文件一个 CLI 插头：导出 `pub const FOO: RuntimeDefinition`。  
`build_args` 函数指针指向 `build_args.rs`；`discover_models` 组合 [../model_discover/README.md](../model_discover/README.md)。

新增：本目录加 `<id>.rs` → `mod.rs` `pub use` → [../registry.rs](../registry.rs) 登记。不要在业务里 match id。

`external_mcp_injection` 有的 CLI 已声明（如 `claude-mcp-json`），见 [../mcp/README.md](../mcp/README.md)。已实现：Codex / OpenCode / Claude（CodeBuddy 同模式）；未实现的模式会打日志后跳过。

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

### `codex.rs`

`CODEX`，id `codex`。`external_mcp_injection: Some("codex-mcp")`。模型：`login status` 成功则 `debug models`，否则静态列表。

### `claude.rs`

`CLAUDE`，id `claude`。stream-json。注入标记 `claude-mcp-json`（cwd `.mcp.json`）。

### `opencode.rs`

`OPENCODE`，id `opencode`。注入 `opencode-env-content`。

### `cursor.rs`

`CURSOR`，id `cursor-agent`。二进制 `cursor-agent`。解析走 Codex 同类 JSON。

### `mimo.rs`

`MIMO`，id `mimo`。注入标记 `mimo-env-content`（尚未实现）。

### `deepseek.rs`

`DEEPSEEK`，id `deepseek`（CodeWhale 一类）。

### `deepseek_harness.rs`

`DEEPSEEK_HARNESS`，id `deepseek-harness`，二进制 `dsh`。带 validate + DSH 模型发现。

### `qwen.rs`

`QWEN`，id `qwen`。

### `qoder.rs`

`QODER`，id `qoder`。stdout 近 Claude stream-json。

### `grok.rs`

`GROK`，id `grok-build`。ACP 发现模型。

### `pi.rs`

`PI`，id `pi`。

### `trae.rs`

`TRAE`，id `trae-cli`。注入标记 `acp-merge`（尚未实现）。

### `codebuddy.rs`

`CODEBUDDY`，id `codebuddy`。注入标记 `claude-mcp-json`（与 Claude 同实现）。

## 子目录

无。
