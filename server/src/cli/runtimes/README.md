# cli/runtimes

CLI 插头：每个外部 CLI 一个文件，实现 [../base.py](../base.py) 的 `CliRuntime`。

只写差异 —— `id` / `name` / `binary` / `path_env` / `mcp_mode` / `stream_format` 与 `build_args`；
生命周期、二进制探测、压缩都在插座里。

## 本目录文件

- `codex.py` — `CodexRuntime`：`codex exec`（Windows 上 codex sandbox 收不紧，走 full-access）
- `claude.py` — `ClaudeRuntime`：`claude -p --input-format stream-json`。
  注意 `stdin_format = "claude-stream-json"`：它收的是**一条 JSON 消息**，不是纯文本，
  灌纯文本会报 `Error parsing streaming input line`
- `opencode.py` — `OpenCodeRuntime`：`opencode run --format json --auto --thinking`

## 子目录

无。加新 CLI：本目录加插头 + [../registry.py](../registry.py) 登记一行。

---

## 现状：谁真能拿到 MCP 工具（实测）

| runtime | 注入方式 | 模型看到的工具名 | 能用吗 |
|---|---|---|---|
| **opencode** | `OPENCODE_CONFIG_CONTENT` 设 `mcp.<name>` | `dingda_search` / `dingda_product` / `dingda_compare`… | ✅（默认 agent，程序里跑得通） |
| **claude** | cwd 写 `.mcp.json` | `mcp__dingda__search` 等 | ✅ |
| **codex** | `-c mcp_servers.<n>.*`（逐键点分） | —— | ❌ codex 0.152 只出它自带 bundled 插件的工具；`context7`/`codegraph`/`dingda` 都不出（server 会被 spawn、`mcp list` 认成 enabled、`doctor` 报正常，但工具进不了模型工具表；对应 openai/codex issue #26810） |

**注意工具名按 runtime 不同**：opencode 是 `dingda_<tool>`（下划线），claude 是 `mcp__dingda__<tool>`。
前端 `steps.normalize_tool_name` 已经会剥 `dingda_` / `goofish_` 前缀，所以 opencode 的命名是一直被支持的。

opencode 的 MCP 配置形状（据本地 `@opencode-ai/sdk` 的 `McpLocalConfig` 类型）：

```json
{ "mcp": { "dingda": {
    "type": "local",
    "command": ["uv", "run", "--directory", "<server>", "dingda-mcp"],
    "environment": { "DINGDA_SERVER_DIR": "..." },
    "enabled": true
} } }
```

`command` 就是 **「命令 + 参数」整个数组**，没有单独的 `args` 字段；缺 `type` 会被
`Ignoring MCP config entry without type` 丢掉。

codex 那边：`-c` 的值必须是**单个 TOML 值**，整张内联表会被当字符串（`invalid type: string`），
所以 `inject/mcp.py` 用逐键点分。要让 codex 有工具，目前只能走「prompt 里给 CLI 命令 + shell 调用」
那条退路（见 `cli/repair/README.md`）。
