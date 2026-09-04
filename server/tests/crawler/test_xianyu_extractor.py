"""闲鱼 extractor 单测（不启浏览器）。"""

from __future__ import annotations

from src.crawler.sources.xianyu.extractor import (
    item_from_mtop_detail,
    item_from_view,
    item_id_from_url,
    items_from_payload,
)


def test_item_id_from_url() -> None:
    assert item_id_from_url("https://www.goofish.com/item?id=42&x=1") == "42"
    assert item_id_from_url("bad") == ""


def test_items_from_payload() -> None:
    payload = {
        "items": [
            {
                "title": "手机",
                "url": "https://www.goofish.com/item?id=9",
                "price": "¥100",
                "location": "上海",
            },
            {"title": "", "url": "https://www.goofish.com/item?id=10"},
        ]
    }
    items = items_from_payload(payload)
    assert len(items) == 1
    assert items[0].item_id == "9"
    assert items[0].title == "手机"
    assert items[0].price == "¥100"
    assert items[0].raw.get("location") == "上海"


def test_item_from_mtop_detail() -> None:
    raw = {
        "ret": ["SUCCESS::调用成功"],
        "data": {
            "trackParams": {
                "id": "100",
                "title": "相机",
                "soldPrice": "88",
                "seller_nick": "卖家",
                "itemStatus": "0",
            }
        },
    }
    item = item_from_mtop_detail(raw, "100")
    assert item.item_id == "100"
    assert item.title == "相机"
    assert item.price == "88"
    assert item.raw["seller_nick"] == "卖家"


def test_item_from_view() -> None:
    payload = {
        "item_id": "77",
        "title": "页内相机",
        "price": "¥12",
        "seller_name": "卖家",
        "status": "在售",
    }
    item = item_from_view(payload, "77")
    assert item.item_id == "77"
    assert item.title == "页内相机"
    assert item.price == "¥12"
    assert item.url == "https://www.goofish.com/item?id=77"
    assert item.raw["seller_nick"] == "卖家"
    assert item.raw["view"]["status"] == "在售"
