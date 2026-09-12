"""Tool registry 单测。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from src.crawler.core.types import CrawlItem, CrawlResult
from src.tools.compare import CompareOutput
from src.tools.product import ProductOutput
from src.tools.search import SearchOutput
from src.tools.registry import call_tool, get_tool, list_tools


def test_get_tool() -> None:
    assert get_tool("search").name == "search"
    assert get_tool("product").name == "product"
    assert get_tool("compare").name == "compare"


def test_list_tools_includes_login() -> None:
    names = [s.name for s in list_tools()]
    assert names == [
        "compare",
        "login",
        "preview",
        "product",
        "search",
        "validate_selectors",
    ]
    assert get_tool("login").name == "login"
    # 校验工具只给修复子 agent，不进默认工具面
    assert get_tool("validate_selectors").internal_only is True
    assert get_tool("search").internal_only is False


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


def test_call_search_ali1688_mocked() -> None:
    fake_result = CrawlResult(
        items=[
            CrawlItem(
                item_id="99",
                title="卫衣",
                url="https://detail.1688.com/offer/99.html",
                price="45.5",
            )
        ]
    )

    async def _run() -> None:
        with patch("src.tools.search.create_api_crawler") as create:
            crawler = AsyncMock()
            crawler.search = AsyncMock(return_value=fake_result)
            create.return_value = crawler
            out = await call_tool(
                "search",
                {"platform": "ali1688", "query": "黑色卫衣", "limit": 5},
            )
        assert isinstance(out, SearchOutput)
        assert out.ok is True
        assert len(out.items) == 1
        assert out.items[0].item_id == "99"
        create.assert_called_once_with("ali1688")

    asyncio.run(_run())


def test_call_compare_mocked() -> None:
    from src.crawler.sources.ali1688.compare import CompareResult, CompareSource

    fake = CompareResult(
        items=[
            CrawlItem(
                item_id="1",
                title="A",
                url="https://detail.1688.com/offer/1.html",
                price="10",
                raw={
                    "_compare_label": "价格最低",
                    "_compare_reasons": ["价格最低"],
                    "_compare_score": 91.5,
                    "_compare_round": 2,
                    "supplier": "S",
                    "merchant_rating": 4.8,
                    "similarity_score": 0.96,
                },
            )
        ],
        source=CompareSource(
            item_id="xy-1",
            title="闲鱼露营椅",
            platform="xianyu",
            url="https://www.goofish.com/item?id=xy-1",
            image_url="https://img.alicdn.com/x.jpg",
            price="89",
            seller="山系玩家",
        ),
        source_image="https://img.alicdn.com/x.jpg",
        source_url="https://www.goofish.com/item?id=xy-1",
        total_candidates=5,
        rounds=2,
        queries=["[image]", "露营椅"],
    )

    async def _run() -> None:
        with patch(
            "src.tools.compare.compare_products",
            new=AsyncMock(return_value=fake),
        ):
            out = await call_tool(
                "compare",
                {
                    "image": "https://img.alicdn.com/x.jpg",
                    "source": {
                        "item_id": "xy-1",
                        "title": "闲鱼露营椅",
                        "platform": "xianyu",
                        "url": "https://www.goofish.com/item?id=xy-1",
                        "price": "89",
                    },
                    "rounds": 2,
                    "limit": 3,
                },
            )
        assert isinstance(out, CompareOutput)
        assert out.ok is True
        assert out.kind == "price_compare"
        assert out.platform == "ali1688"
        assert out.source.item_id == "xy-1"
        assert out.rounds == 2
        assert out.queries == ["[image]", "露营椅"]
        assert out.total_candidates == 5
        assert out.items[0].compare_label == "价格最低"
        assert out.items[0].compare_reasons == ["价格最低"]
        assert out.items[0].compare_score == 91.5
        assert out.items[0].merchant_rating == 4.8
        assert out.items[0].round == 2

    asyncio.run(_run())
