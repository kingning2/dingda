"""闲鱼 item 单测（mock mtop）。"""

from __future__ import annotations

from contextlib import nullcontext
from unittest.mock import MagicMock, patch

from src.channels.xianyu.item import delete, extract, items


def test_extract() -> None:
    row = extract(
        {
            "id": "9",
            "title": "手机",
            "priceInfo": {"preText": "¥", "price": "100"},
            "itemStatus": "0",
            "picInfo": {"picUrl": "http://img"},
            "itemLabelDataVO": {
                "labelData": {
                    "r1": {"tagList": [{"data": {"type": "text", "content": "包邮"}}]}
                }
            },
        }
    )
    assert row["item_id"] == "9"
    assert row["price"] == "¥100"
    assert row["status"] == "在售"
    assert row["tags"] == ["包邮"]


def test_items() -> None:
    session = MagicMock()
    session.unb = "u1"
    mtop_raw = {
        "data": {
            "nextPage": False,
            "cardList": [
                {
                    "cardData": {
                        "id": "1",
                        "title": "a",
                        "priceInfo": {"price": "1"},
                        "itemStatus": "0",
                        "picInfo": {},
                    }
                }
            ],
        }
    }
    with (
        patch(
            "src.channels.xianyu.item.Session.from_cookie_header",
            return_value=session,
        ),
        patch("src.channels.xianyu.item.mtop_call", return_value=mtop_raw),
    ):
        out = items("unb=1; _m_h5_tk=a_b", limit=10)
    assert out["total"] == 1
    assert out["items"][0]["item_id"] == "1"
    assert out["items"][0]["rank"] == 1


def test_delete() -> None:
    session = MagicMock()
    with (
        patch(
            "src.channels.xianyu.item.Session.from_cookie_header",
            return_value=session,
        ),
        patch(
            "src.channels.xianyu.item.mtop_call",
            return_value={"ret": ["SUCCESS::ok"]},
        ),
        patch("src.channels.xianyu.item.acquire", return_value=nullcontext()),
        patch("src.channels.xianyu.item.hold", return_value=nullcontext()),
    ):
        out = delete("unb=1; _m_h5_tk=a_b", "99")
    assert out["ok"] is True
    assert out["item_id"] == "99"
