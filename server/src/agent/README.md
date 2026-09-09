# agent

产品侧 Agent（进程内 Tool + Headroom）与外部 CLI Runtime 启动（Python spawn）。  
禁止 import Playwright、Camoufox、`channels.xianyu` / crawler sources。

HTTP：[`../api/agent.py`](../api/agent.py)

- 产品：`POST /v1/agent/works/{work_id}/run` SSE
- CLI：`POST /v1/agent/runtimes/{runtime_id}/run` SSE（codex / claude / opencode）

外部 CLI 不再由 Tauri spawn；MCP 仅服务「Python 拉起的 CLI」。

## 本目录文件

### `__init__.py`

包导出。

## 子目录

- [core/](core/README.md) — `AgentService` / Headroom `compress`
- [runtimes/](runtimes/README.md) — CLI spawn / MCP 注入 / 系统前言 / 流解析
- [workflows/](workflows/README.md) — 调研等多步图
