"""内部 MCP / Tool Registry 测试（不接第三方命令）。"""

from __future__ import annotations

import asyncio

from mcp.server.fastmcp import FastMCP

from src.mcp.catalog import list_builtin_mcp_servers
from src.mcp.register import register_internal_tools
from src.mcp.server import create_mcp_server
from src.tools.search import SearchInput, SearchOutput
from src.tools.registry import call_tool, list_tools


def test_list_tools_only_crawler() -> None:
    names = {spec.name for spec in list_tools()}
    assert names == {"search", "product", "compare"}


def test_register_internal_tools_matches_registry() -> None:
    mcp = FastMCP("dingda")
    registered = set(register_internal_tools(mcp))
    assert registered == {"search", "product", "compare"}


def test_catalog_hint_lists_crawler_tools() -> None:
    servers = list_builtin_mcp_servers()
    assert len(servers) == 1
    hint = str(servers[0]["status"]["hint"])  # type: ignore[index]
    assert "search" in hint
    assert "product" in hint
    assert "compare" in hint
    assert "ali1688" in hint


def test_create_mcp_server_registers_internal() -> None:
    mcp = create_mcp_server()
    assert mcp.name == "dingda"


def test_call_tool_unknown_platform() -> None:
    async def _run() -> None:
        out = await call_tool("search", {"platform": "nope", "query": "手机"})
        assert isinstance(out, SearchOutput)
        assert out.ok is False
        assert out.error_code == "crawler.platform_unsupported"

    asyncio.run(_run())


def test_search_input_schema() -> None:
    inp = SearchInput(platform="xianyu", query="键盘")
    assert inp.proxy_url is None
