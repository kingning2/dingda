"""内部 Tool：选品能力 + registry；供产品 Agent 与 MCP 共用。"""

from __future__ import annotations

from tools.registry import call_tool, get_tool, list_tools

__all__ = ["call_tool", "get_tool", "list_tools"]
