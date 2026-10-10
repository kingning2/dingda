# agent

产品侧 Agent（进程内 LLM + Tool 循环）。  
禁止 import Playwright、Camoufox、`channels.xianyu` / crawler sources。

HTTP：[`../api/agent.py`](../../../api/src/api/agent.py)

- 产品：`POST /v1/agent/works/{work_id}/run` SSE（内置 Agent，模型由 `DINGDA_LLM_*` 决定）

早期的外部 CLI Runtime（codex / claude / opencode）子包已随外部 CLI 支持整体移除。

## 本目录文件

### `__init__.py`

包导出。

## 子目录

- [core/](core/README.md) — `AgentService` / Headroom `compress`
- [workflows/](workflows/README.md) — 调研等多步图
