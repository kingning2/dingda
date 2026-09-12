"""1688 extractor / link / compare 选品单测。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from src.crawler.core.types import CrawlItem, CrawlResult
from src.crawler.sources.ali1688.compare import select_top
from src.crawler.sources.ali1688.extractor import item_from_api, items_from_api
from src.crawler.sources.ali1688.link import parse_product_ref


def test_item_from_api() -> None:
    raw = {
        "itemId": 984731164094,
        "title": "按摩垫",
        "imageUrl": "https://img.alicdn.com/a.jpg",
        "detailUrl": "https://detail.1688.com/offer/984731164094.html",
        "score": "0.97",
        "currentPrice": 45.5,
        "skuId": 6052056270674,
        "skuTitle": "黑色 XL",
        "yxIndex": 4.9,
        "quantityBegin": 2,
        "unit": "件",
        "company": "广州某服饰",
        "soldOut": 50000,
        "storeAmount": 12000,
        "promotionTags": ["满99减5"],
        "serviceInfos": [{"type": "发货保障", "value": "48小时发货"}],
        "sellingPoints": [{"type": "industryCPV", "value": "加绒"}],
    }
    item = item_from_api(raw)
    assert item.item_id == "984731164094"
    assert item.title == "按摩垫"
    assert item.price == "45.5"
    assert item.raw["supplier"] == "广州某服饰"
    assert item.raw["sold_count"] == 50000
    assert item.raw["yx_index"] == 4.9


def test_items_from_api_filters_empty() -> None:
    rows = [
        {"itemId": "", "title": "", "detailUrl": ""},
        {"itemId": 1, "title": "有货", "currentPrice": 1},
    ]
    items = items_from_api(rows)
    assert len(items) == 1
    assert items[0].item_id == "1"


def test_parse_product_ref_1688_url() -> None:
    parsed = parse_product_ref("https://detail.1688.com/offer/895657286458.html")
    assert parsed["platform"] == "1688"
    assert parsed["product_id"] == "895657286458"
    assert "895657286458" in parsed["canonical_url"]


def test_parse_product_ref_pure_id() -> None:
    parsed = parse_product_ref("895657286458")
    assert parsed["platform"] == "1688"


def test_select_top_labels() -> None:
    products = [
        CrawlItem(
            item_id="a",
            title="贵且好卖",
            url="https://detail.1688.com/offer/a.html",
            price="100",
            raw={"sold_count": 1000, "yx_index": 3.0},
        ),
        CrawlItem(
            item_id="b",
            title="便宜",
            url="https://detail.1688.com/offer/b.html",
            price="10",
            raw={"sold_count": 10, "yx_index": 2.0},
        ),
        CrawlItem(
            item_id="c",
            title="严选",
            url="https://detail.1688.com/offer/c.html",
            price="50",
            raw={"sold_count": 50, "yx_index": 5.0},
        ),
    ]
    top = select_top(products, limit=3)
    labels = {p.item_id: p.raw["_compare_label"] for p in top}
    assert labels["a"] == "销量最高"
    assert labels["b"] == "价格最低"
    assert labels["c"] == "综合最优"
    assert top[0].raw["_compare_score"] is not None
    assert top[0].raw["_compare_reasons"] == ["销量最高"]


def test_select_top_merge_labels() -> None:
    products = [
        CrawlItem(
            item_id="one",
            title="全能",
            url="https://detail.1688.com/offer/one.html",
            price="1",
            raw={"sold_count": 999, "yx_index": 9.9},
        ),
    ]
    top = select_top(products, limit=3)
    assert len(top) == 1
    assert "销量最高" in top[0].raw["_compare_label"]
    assert "价格最低" in top[0].raw["_compare_label"]
    assert "综合最优" in top[0].raw["_compare_label"]


def test_compare_products_mocked() -> None:
    fake = CrawlResult(
        items=[
            CrawlItem(
                item_id="1",
                title="A",
                url="https://detail.1688.com/offer/1.html",
                price="20",
                raw={"sold_count": 100, "yx_index": 4.0, "supplier": "S"},
            ),
            CrawlItem(
                item_id="2",
                title="B",
                url="https://detail.1688.com/offer/2.html",
                price="5",
                raw={"sold_count": 10, "yx_index": 3.0},
            ),
        ]
    )

    async def _run() -> None:
        with patch(
            "src.crawler.sources.ali1688.compare.Ali1688Crawler"
        ) as crawler_cls:
            instance = AsyncMock()
            instance.search = AsyncMock(return_value=fake)
            crawler_cls.return_value = instance
            from src.crawler.sources.ali1688.compare import compare_products

            out = await compare_products(image="https://img.alicdn.com/x.jpg", limit=3)
        assert out.total_candidates == 2
        assert out.source_image == "https://img.alicdn.com/x.jpg"
        assert len(out.items) >= 1

    asyncio.run(_run())


def test_compare_products_multi_round_and_source() -> None:
    first = CrawlResult(
        items=[
            CrawlItem(
                item_id="1",
                title="露营椅 折叠便携",
                url="https://detail.1688.com/offer/1.html",
                price="40",
                raw={
                    "score": 0.96,
                    "sold_count": 100,
                    "yx_index": 4.0,
                    "supplier": "S",
                },
            )
        ]
    )
    second = CrawlResult(
        items=[
            CrawlItem(
                item_id="2",
                title="露营椅 加厚",
                url="https://detail.1688.com/offer/2.html",
                price="35",
                raw={
                    "score": 0.93,
                    "sold_count": 300,
                    "yx_index": 4.8,
                    "supplier": "T",
                },
            )
        ]
    )

    async def _run() -> None:
        with patch(
            "src.crawler.sources.ali1688.compare.Ali1688Crawler"
        ) as crawler_cls:
            instance = AsyncMock()
            instance.search = AsyncMock(side_effect=[first, second])
            crawler_cls.return_value = instance
            from src.crawler.sources.ali1688.compare import compare_products

            out = await compare_products(
                image="https://img.alicdn.com/x.jpg",
                source_item={
                    "item_id": "xy-1",
                    "title": "闲鱼露营椅",
                    "platform": "xianyu",
                    "url": "https://www.goofish.com/item?id=xy-1",
                    "price": "89",
                    "seller": "山系玩家",
                },
                limit=3,
                rounds=2,
            )
        assert out.rounds == 2
        assert out.total_candidates == 2
        assert out.source.item_id == "xy-1"
        assert out.source.platform == "xianyu"
        assert out.source.price == "89"
        assert len(out.queries) == 2
        assert out.queries[0] == "[image]"
        assert "露营椅" in out.queries[1]
        assert instance.search.await_count == 2
        first_ctx = instance.search.await_args_list[0].args[0]
        second_ctx = instance.search.await_args_list[1].args[0]
        assert first_ctx.meta["mode"] == "image"
        assert second_ctx.meta["mode"] == "text"

    asyncio.run(_run())
