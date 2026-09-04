"""Tool registry 单测。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from src.crawler.core.types import CrawlItem, CrawlResult
from src.tools.product import ProductOutput
from src.tools.search import SearchOutput
from src.tools.registry import call_tool, get_tool, list_tools


def test_get_tool() -> None:
    assert get_tool("search").name == "search"
    assert get_tool("product").name == "product"


def test_list_tools_only_search_product() -> None:
    names = [s.name for s in list_tools()]
    assert names == ["product", "search"]


def test_call_unsupported_platform() -> None:
    async def _run() -> None:
        out = await call_tool("search", {"platform": "nope", "query": "x"})
        assert isinstance(out, SearchOutput)
        assert out.ok is False

    asyncio.run(_run())


def test_call_product_unsupported_platform() -> None:
    async def _run() -> None:
        out = await call_tool(
            "product",
            {"platform": "nope", "item_id": "1", "cookie": "unb=1; _m_h5_tk=a_b"},
        )
        assert isinstance(out, ProductOutput)
        assert out.ok is False
        assert out.error_code == "crawler.platform_unsupported"

    asyncio.run(_run())


def test_call_product_success_mocked() -> None:
    fake_result = CrawlResult(
        items=[
            CrawlItem(
                item_id="1",
                title="t",
                url="https://www.goofish.com/item?id=1",
                price="1",
                raw={"seller_nick": "s", "status": "0"},
            )
        ]
    )

    async def _run() -> None:
        with (
            patch(
                "src.tools.product.get_browser_manager",
            ) as get_manager,
            patch("src.tools.product.create_crawler") as create,
        ):
            manager = AsyncMock()
            get_manager.return_value = manager
            crawler = AsyncMock()
            crawler.detail = AsyncMock(return_value=fake_result)
            create.return_value = crawler
            out = await call_tool(
                "product",
                {
                    "platform": "xianyu",
                    "item_id": "1",
                    "cookie": "unb=1; _m_h5_tk=a_b",
                },
            )
        assert isinstance(out, ProductOutput)
        assert out.ok is True
        assert out.item is not None
        assert out.item.title == "t"

    asyncio.run(_run())
