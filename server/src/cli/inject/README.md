# cli/inject

把 dingda-mcp 注入外部 CLI。

## 本目录文件

- `mcp.py` — `apply_mcp_inject(mode, *, cwd, args, env, run_id, api_base)`：claude 写 cwd `.mcp.json`；
  codex 加 `-c mcp_servers.dingda=...`；opencode 设 `OPENCODE_CONFIG_CONTENT`；
  `mode="none"` 直接返回不注入（子 agent 用）。

## 子目录

无。
