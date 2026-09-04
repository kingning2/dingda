"""DingDa MCP — 向外部 Agent 暴露内部 Tool（经 registry，不接第三方命令）。"""

from src.mcp.catalog import list_builtin_mcp_servers
from src.mcp.server import create_mcp_server, main

__all__ = ["create_mcp_server", "list_builtin_mcp_servers", "main"]
