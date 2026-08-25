"""LangGraph agent 模块 — Python 侧 AI 编排。

当前为脚手架：最小 `planner → final` 图，经 OpenAI 兼容接口调用 LLM。
后续按需接入意图识别、知识注入、搜索工具、多 provider 等。
"""

from sidecar.agents.graph import run_reply

__all__ = ["run_reply"]
