# agent/core

Agent 运行生命周期。

## 本目录文件

### `agent.py`

`AgentService`：收用户目标 → `tools.registry.call_tool` → Headroom → OpenAI-compatible LLM → 事件流。

### `__init__.py`

包标记。

## 子目录

无。工具列表：[../../tools/README.md](../../../../tools/src/tools/README.md)。上下文压缩在 `packages-py/core/src/core/compress.py`；外部 CLI Runtime（非本包）见 [cli/runtimes](../../../../cli/src/cli/runtimes/README.md)。
