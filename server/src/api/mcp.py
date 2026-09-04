"""MCP 服务发现 HTTP 路由。"""

from __future__ import annotations

from fastapi import APIRouter

from src.mcp.catalog import list_builtin_mcp_servers

router = APIRouter(prefix="/v1/mcp", tags=["mcp"])


@router.get("/servers")
def list_mcp_servers() -> dict[str, list[dict[str, object]]]:
    """列出 DingDa 内置 MCP server（供桌面端注入 Codex / 设置页展示）。"""
    return {"servers": list_builtin_mcp_servers()}
