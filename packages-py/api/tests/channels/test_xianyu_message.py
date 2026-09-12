"""闲鱼 message 封装单测（mock mtop / ws）。"""

from __future__ import annotations

import asyncio
from contextlib import nullcontext
from unittest.mock import AsyncMock, MagicMock, patch

from channels.xianyu.message import chats, parse_session_row, send


def test_parse_session_row() -> None:
    row = parse_session_row(
        {
            "session": {
                "sessionId": "s1",
                "sessionType": 1,
                "userInfo": {"nick": "对方", "userId": "u2"},
            },
            "message": {"summary": {"unread": 2, "summary": "你好", "ts": 9}},
        }
    )
    assert row["session_id"] == "s1"
    assert row["peer_nick"] == "对方"
    assert row["unread"] == 2
    assert row["source"] == "baseline"


def test_chats_baseline() -> None:
    session = MagicMock()
    mtop_raw = {
        "data": {
            "hasMore": False,
            "sessions": [
                {
                    "session": {
                        "sessionId": "s1",
                        "sessionType": 1,
                        "userInfo": {"nick": "n", "userId": "u"},
                    },
                    "message": {"summary": {"unread": 0, "summary": "hi", "ts": 1}},
                }
            ],
        }
    }

    async def _run() -> None:
        with (
            patch(
                "channels.xianyu.message.Session.from_cookie_header",
                return_value=session,
            ),
            patch(
                "channels.xianyu.message.mtop_call",
                return_value=mtop_raw,
            ),
        ):
            out = await chats("unb=1; _m_h5_tk=a_b", fetch_num=10, watch_secs=0)
        assert out["total"] == 1
        assert out["sessions"][0]["session_id"] == "s1"
        assert out["from_watch"] == 0

    asyncio.run(_run())


def test_send_text() -> None:
    session = MagicMock()
    session.unb = "me"

    async def _run() -> None:
        with (
            patch(
                "channels.xianyu.message.Session.from_cookie_header",
                return_value=session,
            ),
            patch(
                "channels.xianyu.message.get_access_token",
                return_value="tok",
            ),
            patch("channels.xianyu.message.connect") as connect_cm,
            patch(
                "channels.xianyu.message.register",
                new_callable=AsyncMock,
            ),
            patch(
                "channels.xianyu.message.heartbeat_loop",
                new_callable=AsyncMock,
            ),
            patch(
                "channels.xianyu.message.send_text",
                new_callable=AsyncMock,
                return_value="mid-1",
            ),
            patch("channels.xianyu.message.asyncio.sleep", new_callable=AsyncMock),
            patch("channels.xianyu.message.acquire", return_value=nullcontext()),
            patch("channels.xianyu.message.hold", return_value=nullcontext()),
        ):
            ws = MagicMock()
            connect_cm.return_value.__aenter__ = AsyncMock(return_value=ws)
            connect_cm.return_value.__aexit__ = AsyncMock(return_value=None)
            out = await send(
                "unb=1; _m_h5_tk=a_b",
                cid="c1",
                toid="u2",
                text="hello",
            )
        assert out["ok"] is True
        assert out["mid"] == "mid-1"

    asyncio.run(_run())
