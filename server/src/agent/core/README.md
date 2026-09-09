# agent/core

Agent 运行生命周期与上下文压缩。

## 本目录文件

### `agent.py`

`AgentService`：收用户目标 → `tools.registry.call_tool` → Headroom → OpenAI-compatible LLM → 事件流。

### `compress.py`

`compress_messages` / `compress_tool_payload`；`DINGDA_HEADROOM=0` 关闭。

### `__init__.py`

包标记。

## 子目录

无。工具列表：[../../tools/README.md](../../tools/README.md)。Runtime：[../runtimes/README.md](../runtimes/README.md)。
