"""闲鱼搜索 MTOP 解析单元测试。

用 fixture JSON 校验 ``parse_search_items`` / ``map_item`` 边界行为。"""

from __future__ import annotations

from crawlers.xianyu.search.mtop import map_item, parse_search_items

FIXTURE = {
    "data": {
        "resultList": [
            {
                "data": {
                    "item": {
                        "main": {
                            "exContent": {
                                "title": "Sony A7M4 Body",
                                "price": [{"text": "¥"}, {"text": "13999"}],
                                "area": "上海",
                                "userNickName": "seller_01",
                                "picUrl": "https://img.example.com/a7m4.jpg",
                                "itemId": "123456",
                                "oriPrice": "¥16999",
                                "fishTags": {
                                    "r1": {
                                        "tagList": [{"data": {"content": "验货宝"}}],
                                    },
                                },
                            },
                            "clickParam": {
                                "args": {
                                    "publishTime": "1710000000000",
                                    "wantNum": 12,
                                    "tag": "freeship",
                                },
                            },
                            "targetUrl": "fleamarket://item?id=123456",
                        },
                    },
                },
            },
        ],
    },
}


def test_parse_search_items_from_fixture() -> None:
    items = parse_search_items(FIXTURE)
    assert len(items) == 1
    item = items[0]
    assert item["itemId"] == "123456"
    assert item["title"] == "Sony A7M4 Body"
    assert item["url"] == "https://www.goofish.com/item?id=123456"
    assert item["price"]["text"] == "¥13999"
    assert item["location"] == "上海"
    assert item["seller"]["name"] == "seller_01"
    assert "包邮" in item["tags"]
    assert "验货宝" in item["tags"]
    assert item["wantCount"] == "12"


def test_map_item_returns_none_without_id() -> None:
    assert map_item({"data": {"item": {"main": {"exContent": {"title": "x"}}}}}) is None
