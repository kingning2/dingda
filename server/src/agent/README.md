# agent

产品侧 Agent：规划、经 `tools.registry.call_tool` 调能力、调研 workflow。  
禁止 import Playwright、Camoufox、sqlite、`channels.xianyu`。

HTTP 入口将来是 `api/agent.py`（现为空骨架）。外部 Codex 不走本包，走 MCP。

## 本目录文件

### `__init__.py`

包导出。实现在子目录。

## 子目录

- [core/](core/README.md) — 执行循环 / `AgentService`
- [workflows/](workflows/README.md) — 调研等多步图
