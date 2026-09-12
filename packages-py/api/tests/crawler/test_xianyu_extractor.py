"""闲鱼 extractor 单测（不启浏览器）。"""

from __future__ import annotations

from crawler.sources.xianyu.extractor import (
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
                "image_url": "//img.test/a.jpg",
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
    assert items[0].raw.get("image_url") == "https://img.test/a.jpg"


def test_item_from_mtop_detail() -> None:
    raw = {
        "ret": ["SUCCESS::调用成功"],
        "data": {
            "itemDO": {
                "itemId": "100",
                "title": "相机",
                "soldPrice": "88",
                "wantCnt": 15,
                "browseCnt": 200,
                "itemStatusStr": "在售",
                "imageInfos": [{"url": "//gw.test/cam.jpg"}],
            },
            "sellerDO": {"nick": "卖家"},
            "trackParams": {
                "id": "100",
                "title": "相机-track",
                "soldPrice": "1",
            },
        },
    }
    item = item_from_mtop_detail(raw, "100")
    assert item.item_id == "100"
    assert item.title == "相机"
    assert item.price == "¥88"
    assert item.raw["seller_nick"] == "卖家"
    assert item.raw["want_count"] == "15"
    assert item.raw["browse_count"] == "200"
    assert item.raw["image_url"] == "https://gw.test/cam.jpg"


def test_item_from_view() -> None:
    payload = {
        "item_id": "77",
        "title": "页内相机",
        "price": "¥12",
        "seller_name": "卖家",
        "status": "在售",
        "want_count": "9",
        "image_urls": ["https://img.test/view.jpg"],
    }
    item = item_from_view(payload, "77")
    assert item.item_id == "77"
    assert item.title == "页内相机"
    assert item.price == "¥12"
    assert item.url == "https://www.goofish.com/item?id=77"
    assert item.raw["seller_nick"] == "卖家"
    assert item.raw["want_count"] == "9"
    assert item.raw["image_url"] == "https://img.test/view.jpg"
    assert item.raw["view"]["status"] == "在售"
