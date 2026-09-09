"""闲鱼 crawler 风控恢复单测（不启浏览器）。"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from src.crawler.core.types import CrawlContext
from src.crawler.sources.xianyu import crawler as xianyu_crawler
from src.crawler.sources.xianyu.crawler import XianyuCrawler
from src.shared.errors import AppError


class _FakePage:
    """最小 Page：raw/context/url + goto/close。"""

    def __init__(self, *, url: str = "https://www.goofish.com/search?q=t") -> None:
        self.url = url
        self.raw = SimpleNamespace(
            wait_for_timeout=AsyncMock(),
            evaluate=AsyncMock(),
            reload=AsyncMock(),
        )
        self.context = object()
        self.closed = False

    async def goto(self, url: str, *, params: dict[str, str] | None = None, **_: Any) -> None:
        q = (params or {}).get("q", "")
        self.url = f"{url}?q={q}" if q else url

    async def close(self) -> None:
        self.closed = True


def test_search_passes_slider_when_blocked() -> None:
    async def _run() -> None:
        page = _FakePage()
        page.raw.evaluate = AsyncMock(
            side_effect=[
                None,  # SCROLL_JS
                {
                    "requiresAuth": False,
                    "blocked": True,
                    "empty": False,
                    "items": [],
                },
                None,  # SCROLL_JS after recovery
                {
                    "requiresAuth": False,
                    "blocked": False,
                    "empty": False,
                    "items": [
                        {
                            "title": "手机",
                            "url": "https://www.goofish.com/item?id=9",
                            "price": "¥100",
                            "image_url": "https://img.test/a.jpg",
                        }
                    ],
                },
            ]
        )
        browser = SimpleNamespace()
        crawler = XianyuCrawler(browser)  # type: ignore[arg-type]
        crawler.open_page = AsyncMock(return_value=page)  # type: ignore[method-assign]
        crawler.close_page = AsyncMock()  # type: ignore[method-assign]

        with (
            patch.object(xianyu_crawler, "auto_slider_enabled", return_value=True),
            patch.object(xianyu_crawler, "clear_risk_cookies", new_callable=AsyncMock) as clear_ck,
            patch.object(
                xianyu_crawler,
                "try_solve_slider",
                new_callable=AsyncMock,
                return_value=(True, "自动滑块验证成功"),
            ) as solve,
            patch("src.crawler.core.live.emit_live_frame", new_callable=AsyncMock),
            patch("src.crawler.core.live.live_frame_pump", new_callable=AsyncMock) as pump,
        ):
            pump.return_value = SimpleNamespace(aclose=AsyncMock())
            result = await crawler.search(CrawlContext(task_id="t1", meta={"limit": 5}), "手机")

        assert len(result.items) == 1
        assert result.items[0].item_id == "9"
        assert result.items[0].raw.get("image_url") == "https://img.test/a.jpg"
        clear_ck.assert_awaited()
        solve.assert_awaited_once()
        assert solve.await_args.kwargs.get("prefer_page_mouse") is True

    asyncio.run(_run())


def test_search_raises_when_slider_fails() -> None:
    async def _run() -> None:
        page = _FakePage(url="https://www.goofish.com/search?q=t")

        async def _goto_punish(url: str, *, params: dict[str, str] | None = None, **_: Any) -> None:
            del url, params
            page.url = "https://passport.goofish.com/_____tmd_____/punish"

        page.goto = _goto_punish  # type: ignore[method-assign]
        page.raw.evaluate = AsyncMock()
        browser = SimpleNamespace()
        crawler = XianyuCrawler(browser)  # type: ignore[arg-type]
        crawler.open_page = AsyncMock(return_value=page)  # type: ignore[method-assign]
        crawler.close_page = AsyncMock()  # type: ignore[method-assign]

        with (
            patch.object(xianyu_crawler, "auto_slider_enabled", return_value=True),
            patch.object(xianyu_crawler, "clear_risk_cookies", new_callable=AsyncMock),
            patch.object(
                xianyu_crawler,
                "try_solve_slider",
                new_callable=AsyncMock,
                return_value=(False, "自动滑块失败"),
            ) as solve,
            patch("src.crawler.core.live.emit_live_frame", new_callable=AsyncMock),
            patch("src.crawler.core.live.live_frame_pump", new_callable=AsyncMock) as pump,
            pytest.raises(AppError) as raised,
        ):
            pump.return_value = SimpleNamespace(aclose=AsyncMock())
            await crawler.search(CrawlContext(task_id="t2", meta={"limit": 5}), "手机")

        assert raised.value.code == "channel.risk"
        solve.assert_awaited_once()

    asyncio.run(_run())
