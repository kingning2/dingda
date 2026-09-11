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
- `workbuddy.py` — `WorkBuddyRuntime`：WorkBuddy（CodeBuddy Code）的
  `node <install>/resources/app.asar.unpacked/cli/dist/codebuddy.js -p --output-format stream-json`。
  入口是 node 脚本，故 `binary = "node"`、脚本路径由 `build_args` 补在最前；
  `mcp_mode = "none"`，工具走 skill（见下）。

## 子目录

无。加新 CLI：本目录加插头 + [../registry.py](../registry.py) 登记一行。

---

## 工具注入：skill（当前唯一的取证路径）

**不再往各 CLI 注入 MCP。** 工具由 [`../../tools/skill.py`](../../tools/skill.py) 渲染成一份
`SKILL.md`，装到各 runtime 的 skills 目录，agent 自己读、自己 `shell` 调 CLI：

```
python -m src.tools.skill --install
```

写入位置（相对用户主目录）：

| runtime | skills 目录 |
|---|---|
| codex | `.codex/skills/dingda-crawl/SKILL.md` |
| opencode | `.config/opencode/skills/dingda-crawl/SKILL.md` |
| claude | `.claude/skills/dingda-crawl/SKILL.md` |
| **workbuddy** | `.codebuddy/skills/dingda-crawl/SKILL.md` |

命令形态是 `"<python>" -m src.tools.cli <tool> --flags`，stdout 纯 JSON。
渲染时按 `list_tools()` 自动生成工具清单，加工具不用改文档。

**会话角色也不同了**（见 [../roles/README.md](../roles/README.md)）：
子 agent 的 `mcp_mode()` 直接返回 `"none"` —— 工具就是 prompt 里写死的那一条
`python -m src.tools.validate_cli`；比 MCP 白名单更窄，也不会带上别的工具。

> 历史：`inject/mcp.py` 的 `codex-mcp` / `claude-mcp-json` / `opencode-env-content`
> 分支保留但已不在主链路上（`base.py` 仍会调 `apply_mcp_inject`，`mcp_mode="none"` 时直接返回）。
> 真机上 codex 那条本来也出不来工具（见下表），skill 路径是唯一全线可用的。

