# cli/repair

DOM 修复子 agent 的 CLI 侧。

## 本目录文件

- `propose.py` — `propose_dom_patch(snap, validate_url=None)`：把 `DomSnapshot` 发给外部 CLI
  （`run_cli(..., role="child")`），从 stdout 抠出 JSON 选择器补丁写回 `DomPatch`。
  prompt 里的 `dom_tree` 先过插头的 `compress_payload`；只收本 section 已有的字段名。

### 子 agent 怎么自验

给了 `validate_url` 就把「修复现场」告诉它；子 agent 只走**一条**路：

1. **CLI**：prompt 里给出
   `"<python>" -m tools.validate_cli --selectors '<JSON>'`，子 agent 在 shell 里跑；
   回打宿主进程起的校验桥（见 `crawler/extraction/repair/bridge.py`）。
   `DINGDA_VALIDATE_URL` 由 `propose_dom_patch` 直接塞进 CLI 子进程环境。

> 注入方式已统一为 **skill**，子 agent 的 `mcp_mode()` 返回 `"none"` —— 不注入任何工具总线，
> 工具面就是 prompt 里写死的那一条命令行，比工具总线白名单更窄。
> 工具命名、装法见 [../runtimes/README.md](../runtimes/README.md)。

编排（指纹 → AI 轮 → 验证 → 写回）在 `crawler/extraction/repair/`。

## 子目录

无。
