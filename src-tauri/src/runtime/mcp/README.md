# runtime/mcp

启动外部 CLI **这一次进程**时注入叮答爬虫 MCP（`uv run --directory <server> dingda-mcp`）。  
MCP 进程内只暴露 **search / product**；不写用户全局配置，不拼 Skill。

`invocation.rs` 在 spawn 前调 `apply_external_mcp_injection`。definition 上的 `external_mcp_injection` 字符串必须和本目录 `match` 一致，否则只打日志。

## 本目录文件

### `mod.rs`

按 mode 分发：

| mode | 实现 | 谁声明 |
|------|------|--------|
| `codex-mcp` | `codex::apply` | `CODEX` |
| `opencode-env-content` | `opencode::apply` | `OPENCODE` |
| `mimo-env-content` | `mimo::apply` | `MIMO` |
| `claude-mcp-json` | `claude::apply` | `CLAUDE` / `CODEBUDDY` / `QODER` / `GROK` |
| `cursor-mcp-json` | `cursor::apply` | `CURSOR` |
| `qwen-settings-json` | `qwen::apply` | `QWEN` |
| `pi-mcp-json` | `pi::apply` | `PI` |
| `deepseek-mcp-config` | `deepseek::apply` | `DEEPSEEK` |
| `acp-merge` | `acp::apply` | `TRAE` |

`DEEPSEEK_HARNESS`（dsh）保持 `None`：MCP 走 Cordis YAML 插件，不是 mcpServers JSON。

### `goofish.rs`

名字历史原因仍叫 goofish：实际是 **叮答爬虫 MCP**。

- `dingda_mcp_uv_command()` / `stdio_mcp_entry()` / `merge_mcp_servers_file()`
- `codex_mcp_override()` / `opencode_style_config_content()` / `acp_mcp_servers()`
- `SERVER_NAME` — 显示名仍为 `goofish`

server 目录不存在则跳过注入并 log（OpenCode / MiMo **不**设空 `*_CONFIG_CONTENT`）。

### `codex.rs` / `opencode.rs` / `mimo.rs` / `claude.rs` / `cursor.rs` / `qwen.rs` / `pi.rs` / `deepseek.rs` / `acp.rs`

各 mode 的 `apply`：见上表。`acp` 只填 `acp_mcp_servers`；握手在 [`../process.rs`](../process.rs)。

## 子目录

无。Python 侧 MCP：[../../../server/src/mcp/README.md](../../../server/src/mcp/README.md)。
