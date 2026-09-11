# cli/repair

DOM 修复子 agent 的 CLI 侧。

## 本目录文件

- `propose.py` — `propose_dom_patch(snap, validate_url=None)`：把 `DomSnapshot` 发给外部 CLI
  （`run_cli(..., role="child")`），从 stdout 抠出 JSON 选择器补丁写回 `DomPatch`。
  prompt 里的 `dom_tree` 先过插头的 `compress_payload`；只收本 section 已有的字段名。

### 子 agent 怎么自验

给了 `validate_url` 就把「修复现场」告诉它，两条路**都保留**，哪个能用用哪个：

1. **CLI（当前 codex 上实际生效的）**：prompt 里给出
   `"<python>" -m src.tools.validate_cli --selectors '<JSON>'`，子 agent 在 shell 里跑；
   回打宿主进程起的校验桥（见 `crawler/extraction/repair/bridge.py`）。
2. **MCP**：注入 `mcp_servers.dingda`，`DINGDA_MCP_TOOLS` 白名单只放 `validate_selectors`。

> 现状：本机 `codex-cli 0.152.0` **不把外部 MCP server 的工具暴露给模型**
> （`context7` / `codegraph` / 我们的 `dingda` 都一样；只有它自带的 `cua_repl` 插件能出工具），
> 所以 MCP 那条目前是备而不用的。`inject/mcp.py` 已按官方口径改用**逐键点分 `-c`**
> （内联表会被当成字符串，报 `invalid type: string ... in mcp_servers.dingda`）。

编排（指纹 → AI 轮 → 验证 → 写回）在 `crawler/extraction/repair/`。

## 子目录

无。
