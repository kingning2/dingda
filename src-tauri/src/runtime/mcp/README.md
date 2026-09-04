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
| `claude-mcp-json` | `claude::apply` | `CLAUDE` / `CODEBUDDY` |
| 其它（`mimo-env-content`、`acp-merge`） | 未实现，跳过 | 对应 defs |

### `goofish.rs`

名字历史原因仍叫 goofish：实际是 **叮答爬虫 MCP**。

- `dingda_mcp_uv_command()` — `["uv","run","--directory", server, "dingda-mcp"]`
- `codex_mcp_override()` — Codex `-c` 用的 TOML 片段
- `SERVER_NAME` — MCP 里显示名仍为 `goofish`（与旧 Codex 配置兼容）

server 目录不存在则跳过注入并 log（OpenCode **不**设空 `OPENCODE_CONFIG_CONTENT`）。

### `codex.rs`

`apply`：把 override 插到 `args` 最前（`-c` + TOML），并设 `PYTHONUTF8=1`。

### `opencode.rs`

`apply`：写环境变量 `OPENCODE_CONFIG_CONTENT`（内联 JSON local MCP）。无 server 时跳过。

### `claude.rs`

`apply`：在本次 `cwd` 合并写入 `.mcp.json`（只更新 `goofish` 键，保留其它 servers）。

## 子目录

无。Python 侧 MCP：[../../../server/src/mcp/README.md](../../../server/src/mcp/README.md)。
