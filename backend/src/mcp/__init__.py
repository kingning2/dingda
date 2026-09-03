"""DingDa MCP — 向 Codex / Claude / Cursor 暴露爬虫工具（基于 vendored goofish_cli）。"""

from src.mcp.catalog import list_builtin_mcp_servers
from src.mcp.server import create_mcp_server, main

__all__ = ["create_mcp_server", "list_builtin_mcp_servers", "main"]
