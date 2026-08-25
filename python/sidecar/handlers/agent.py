"""LangGraph agent 接口 — 兼容层，委托 ``runtime.handlers.agent``。

旧 handler 路径继续可用，实际逻辑在 runtime handlers。"""

from runtime.handlers.agent import handle_agent_ping, handle_agent_reply

__all__ = ["handle_agent_ping", "handle_agent_reply"]
