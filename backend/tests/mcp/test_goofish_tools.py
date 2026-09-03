"""DingDa MCP 工具注册测试。"""

from __future__ import annotations

import pytest

from mcp.server.fastmcp import FastMCP

from src.adapters.registry import is_vendor_installed
from src.mcp.exclusions import DEFAULT_EXCLUDED_TOOLS
from src.mcp.goofish import _tool_name, register_goofish_tools


@pytest.mark.skipif(not is_vendor_installed("goofish_cli"), reason="goofish_cli vendor 未同步")
def test_register_goofish_tools_excludes_guarded_entries() -> None:
    mcp = FastMCP("goofish")
    registered = register_goofish_tools(mcp, excluded=DEFAULT_EXCLUDED_TOOLS)
    assert "auth_status" in registered
    assert "search_items" in registered
    for excluded in DEFAULT_EXCLUDED_TOOLS:
        assert excluded not in registered


def test_tool_name_normalization() -> None:
    assert _tool_name("message", "list-chats") == "message_list_chats"
