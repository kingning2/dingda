# cli/inject

把 dingda-mcp 注入外部 CLI（**历史/备选路径**）。

> 当前主链路用 **skill** 而不是 MCP：工具由 [`../../tools/skill.py`](../../tools/skill.py)
> 渲染成 `dingda-crawl/SKILL.md` 装到各 runtime 的 skills 目录，会话角色的 `mcp_mode()`
> 返回 `"none"`。本目录留给仍需 MCP 的 CLI。

## 本目录文件

- `mcp.py` — `apply_mcp_inject(mode, *, cwd, args, env, run_id, api_base)`：claude 写 cwd `.mcp.json`；
  codex 加 `-c mcp_servers.dingda=...`；opencode 设 `OPENCODE_CONFIG_CONTENT`；
  `mode="none"` 直接返回不注入（子 agent 用）。

## 子目录

无。
