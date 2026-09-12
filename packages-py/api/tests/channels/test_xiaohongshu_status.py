"""小红书登录态探活测试。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from channels.xiaohongshu.status import LOGIN_CHANNEL_SELECTOR, probe


def test_probe_logged_in() -> None:
    page = AsyncMock()
    page.goto = AsyncMock()
    page.evaluate = AsyncMock(return_value=1)
    page.close = AsyncMock()
    port = AsyncMock()
    port.open = AsyncMock(return_value=page)
    manager = AsyncMock()
    manager.acquire = AsyncMock(return_value=port)
    manager.release = AsyncMock()

    with patch("channels.xiaohongshu.status.get_browser_manager", return_value=manager):
        assert asyncio.run(probe("a1=1; web_session=s")) is True

    page.goto.assert_awaited()
    page.evaluate.assert_awaited()
    args = page.evaluate.await_args
    assert args.args[1] == LOGIN_CHANNEL_SELECTOR
    page.close.assert_awaited()
    manager.release.assert_awaited_with(port)


def test_probe_expired() -> None:
    page = AsyncMock()
    page.goto = AsyncMock()
    page.evaluate = AsyncMock(return_value=0)
    page.close = AsyncMock()
    port = AsyncMock()
    port.open = AsyncMock(return_value=page)
    manager = AsyncMock()
    manager.acquire = AsyncMock(return_value=port)
    manager.release = AsyncMock()

    with patch("channels.xiaohongshu.status.get_browser_manager", return_value=manager):
        assert asyncio.run(probe("a1=1; web_session=s")) is False


def test_probe_missing_cookie() -> None:
    assert asyncio.run(probe("a1=only")) is False
