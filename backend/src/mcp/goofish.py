"""将 vendored goofish_cli registry 注册为 FastMCP tools。"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any

from mcp.server.fastmcp import FastMCP

from src.adapters.crawler.goofish import configure_goofish_runtime
from src.adapters.registry import import_vendor, is_vendor_installed
from src.mcp.exclusions import DEFAULT_EXCLUDED_TOOLS


def _tool_name(namespace: str, name: str) -> str:
    return f"{namespace}_{name}".replace("-", "_")


def register_goofish_tools(
    mcp: FastMCP,
    *,
    excluded: frozenset[str] | None = None,
) -> list[str]:
    """扫描 goofish_cli commands 并注册 MCP tool；返回已注册逻辑名列表。"""
    if not is_vendor_installed("goofish_cli"):
        return []

    configure_goofish_runtime()
    import_vendor("goofish_cli")

    from goofish_cli.core import GoofishError, iter_commands
    from goofish_cli.core.registry import discover

    discover()
    skip = excluded if excluded is not None else DEFAULT_EXCLUDED_TOOLS
    registered: list[str] = []

    for cmd in iter_commands():
        tool_name = _tool_name(cmd.namespace, cmd.name)
        if tool_name in skip:
            continue
        _register_command(mcp, cmd, tool_name, GoofishError)
        registered.append(tool_name)

    return registered


def _register_command(mcp: FastMCP, cmd: Any, tool_name: str, error_type: type[Exception]) -> None:
    doc = cmd.description
    sig = inspect.signature(cmd.func)

    async def handler(**kwargs: Any) -> dict[str, Any]:
        try:
            result = await asyncio.to_thread(cmd.func, **kwargs)
            return {"ok": True, "data": result}
        except error_type as exc:
            return {"ok": False, "error_type": type(exc).__name__, "message": str(exc)}

    handler.__name__ = tool_name
    handler.__doc__ = doc
    handler.__signature__ = sig  # type: ignore[attr-defined]

    mcp.tool(name=tool_name, description=doc)(handler)
