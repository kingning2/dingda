"""小红书 extractor 单测（不启浏览器）。"""

from __future__ import annotations

from src.crawler.sources.xiaohongshu.extractor import item_from_detail, items_from_feeds


def test_items_from_feeds_note_card() -> None:
    items = items_from_feeds(
        {
            "items": [
                {
                    "id": "n1",
                    "noteCard": {
                        "displayTitle": "咖啡探店",
                        "user": {"nickname": "阿茶"},
                        "xsecToken": "tok",
                        "cover": {"url": "https://img.test/n1.jpg"},
                    },
                },
                {"id": "skip", "noteCard": {"displayTitle": ""}},
            ]
        },
        limit=10,
    )
    assert len(items) == 1
    assert items[0].item_id == "n1"
    assert items[0].title == "咖啡探店"
    assert items[0].url.endswith("/explore/n1")
    assert items[0].raw["seller_nick"] == "阿茶"
    assert items[0].raw["xsec_token"] == "tok"
    assert items[0].raw["image_url"] == "https://img.test/n1.jpg"


def test_items_from_feeds_limit() -> None:
    rows = [{"id": str(i), "title": f"t{i}"} for i in range(5)]
    items = items_from_feeds({"items": rows}, limit=2)
    assert [i.item_id for i in items] == ["0", "1"]


def test_item_from_detail_nested_note() -> None:
    item = item_from_detail(
        {
            "note": {
                "note": {
                    "noteId": "abc",
                    "title": "详情标题",
                    "user": {"nickname": "作者"},
                }
            }
        },
        "abc",
    )
    assert item.item_id == "abc"
    assert item.title == "详情标题"
    assert item.raw["seller_nick"] == "作者"


def test_item_from_detail_feed_note_card() -> None:
    item = item_from_detail(
        {
            "items": [
                {
                    "model_type": "note",
                    "note_card": {
                        "note_id": "nid1",
                        "title": "弹层标题",
                        "user": {"nickname": "阿茶"},
                        "interact_info": {"liked_count": "12", "collected_count": "3"},
                    },
                }
            ]
        },
        "nid1",
    )
    assert item.item_id == "nid1"
    assert item.title == "弹层标题"
    assert item.raw["seller_nick"] == "阿茶"
    assert item.raw["browse_count"] == "12"
    assert item.raw["want_count"] == "3"
