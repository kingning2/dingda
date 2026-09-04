# agent/core

Agent 运行生命周期。应订阅 `infrastructure.events` 把步骤推给前端 SSE。尚未接 LangGraph。

## 本目录文件

### `agent.py`

`AgentService`：**骨架**。设计上：收用户目标 → 选 Tool → `call_tool` → 汇总。不要 `create_crawler` 或 `XianyuQrChannel`。

### `__init__.py`

包标记。

## 子目录

无。工具列表：[../../tools/README.md](../../tools/README.md)。
