# agent

产品侧 Agent（进程内 LLM + Tool 循环）。  
禁止 import Playwright、Camoufox、`channels.xianyu` / crawler sources。

HTTP：[`../api/agent.py`](../../../api/src/api/agent.py)

- 产品：`POST /v1/agent/works/{work_id}/run` SSE

外部 CLI Runtime（codex / claude / opencode）不在这里，在 [../cli/](../../../cli/src/cli/README.md)。
两者不要混用：本目录是进程内的 Agent，`cli/` 只负责把外部 CLI 拉起来。

## 本目录文件

### `__init__.py`

包导出。

## 子目录

- [core/](core/README.md) — `AgentService` / Headroom `compress`
- [workflows/](workflows/README.md) — 调研等多步图
