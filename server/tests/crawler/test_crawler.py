"""爬虫基类引用 Browser Context 的单测（mock Port）。"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar, Mapping, Sequence
from unittest.mock import patch

import pytest

from src.browser.port import BrowserPort, Cookie, LaunchOptions, Page
from src.crawler.core.base import BrowserSessionOptions
from src.crawler.core.types import CrawlContext
from src.crawler.registry import (
    cookies_for,
    create_api_crawler,
    create_crawler,
    is_api_platform,
    list_platforms,
)
from src.crawler.sources.xianyu.extractor import items_from_payload
from src.shared.errors import AppError


class _FakeRaw:
    def __init__(
        self,
        payload: dict[str, Any],
        views: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.payload = payload
        self.views = views or {}
        self.evaluate_calls: list[Any] = []

    async def wait_for_timeout(self, ms: int) -> None:
        return None

    def on(self, event: str, handler: Any) -> None:
        """小红书截获 response 用；测试无网络事件，注册即忽略。"""
        return None

    def remove_listener(self, event: str, handler: Any) -> None:
        return None

    async def evaluate(self, script: Any, arg: Any = None) -> Any:
        self.evaluate_calls.append((script, arg))
        # SCROLL_JS 参数是 times（int）
        if isinstance(arg, int) and "scrollBy" in str(script):
            return None
        # VIEW_JS 参数是 item_id（str），DETAIL_DOM_JS 是 {"itemId": ...}
        item_id = ""
        if isinstance(arg, str):
            item_id = arg
        elif isinstance(arg, dict):
            item_id = str(arg.get("itemId") or arg.get("noteId") or "")
        if item_id and item_id in self.views:
            return self.views[item_id]
        return self.payload


_SEARCH_PAYLOAD = {
    "requiresAuth": False,
    "blocked": False,
    "empty": False,
    "items": [
        {
            "title": "手机",
            "url": "https://www.goofish.com/item?id=123",
            "price": "¥10",
        }
    ],
}


class _FakePage(Page):
    def __init__(
        self,
        payload: dict[str, Any] | None = None,
        views: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.closed = False
        self._url = "about:blank"
        self.goto_calls: list[tuple[str, Any]] = []
        self.raw = _FakeRaw(payload or _SEARCH_PAYLOAD, views)

    @property
    def url(self) -> str:
        return self._url

    async def goto(self, url: str, **kwargs: Any) -> None:
        self.goto_calls.append((url, kwargs.get("params")))
        self._url = url

    async def content(self) -> str:
        return "<html></html>"

    async def evaluate(self, expression: str, arg: Any = None) -> Any:
        return await self.raw.evaluate(expression, arg)

    async def click(self, selector: str, **kwargs: Any) -> None:
        return None

    async def fill(self, selector: str, value: str, **kwargs: Any) -> None:
        return None

    async def screenshot(self, path: Any = None) -> bytes:
        return b"png"

    async def cookies(self) -> list[Cookie]:
        return []

    async def add_cookies(self, cookies: Any, *, default_domain: str = "") -> None:
        return None

    async def close(self) -> None:
        self.closed = True


class _FakePort(BrowserPort):
    engine: ClassVar[str] = "fake"

    def __init__(
        self,
        payload: dict[str, Any] | None = None,
        views: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        self.payload = payload
        self.views = views
        self.last_open: dict[str, Any] = {}
        self.last_page: _FakePage | None = None

    async def launch(self, options: LaunchOptions | None = None) -> None:
        return None

    async def open(
        self,
        *,
        proxy: str | None = None,
        fingerprint: str | None = None,
        cookies: Sequence[Cookie] | Mapping[str, str] | None = None,
        default_domain: str = "",
    ) -> Page:
        self.last_open = {
            "proxy": proxy,
            "fingerprint": fingerprint,
            "cookies": cookies,
            "default_domain": default_domain,
        }
        self.last_page = _FakePage(self.payload, self.views)
        return self.last_page

    async def close(self) -> None:
        return None


def test_list_platforms() -> None:
    assert "xianyu" in list_platforms()
    assert "xiaohongshu" in list_platforms()
    assert "ali1688" in list_platforms()


def test_is_api_platform() -> None:
    assert is_api_platform("ali1688") is True
    assert is_api_platform("xianyu") is False


def test_create_api_crawler() -> None:
    crawler = create_api_crawler("ali1688")
    assert crawler.platform == "ali1688"


def test_create_crawler_api_only_raises() -> None:
    with pytest.raises(AppError) as exc:
        create_crawler("ali1688", _FakePort())
    assert exc.value.code == "crawler.platform_api_only"


def test_create_crawler_unknown() -> None:
    with pytest.raises(AppError) as exc:
        create_crawler("nope", _FakePort())
    assert exc.value.code == "crawler.platform_unsupported"


def test_context_options_maps_to_browser() -> None:
    port = _FakePort()
    crawler = create_crawler(
        "xianyu",
        port,
        BrowserSessionOptions(
            proxy_url="http://127.0.0.1:7890",
            fingerprint_profile="windows",
            cookies={"a": "1"},
        ),
    )
    opts = crawler.context_options()
    assert opts.proxy_url == "http://127.0.0.1:7890"
    assert opts.fingerprint_profile == "windows"
    assert opts.default_cookie_domain == ".goofish.com"
    assert opts.cookies == {"a": "1"}


def test_open_page_passes_context() -> None:
    port = _FakePort()
    crawler = create_crawler(
        "xianyu",
        port,
        BrowserSessionOptions(proxy_url="http://proxy", cookies={"k": "v"}),
    )

    async def _run() -> None:
        page = await crawler.open_page(CrawlContext(task_id="t1"))
        assert port.last_open["proxy"] == "http://proxy"
        assert port.last_open["default_domain"] == ".goofish.com"
        assert port.last_open["cookies"] == {"k": "v"}
        await crawler.close_page(page)
        assert isinstance(page, _FakePage)
        assert page.closed

    asyncio.run(_run())


def test_xianyu_search_uses_evaluate() -> None:
    port = _FakePort()
    crawler = create_crawler("xianyu", port)

    async def _run() -> None:
        result = await crawler.search(
            CrawlContext(task_id="t2", meta={"limit": 5}),
            "手机",
        )
        assert len(result.items) == 1
        assert result.items[0].item_id == "123"
        assert result.items[0].title == "手机"
        assert port.last_page is not None
        assert port.last_page.closed
        assert port.last_page.goto_calls[0][0] == "https://www.goofish.com/search"
        assert port.last_page.goto_calls[0][1] == {"q": "手机"}
        # EXTRACT_JS 调用携带 limit=5（search_dom_arg）
        assert any(
            isinstance(call[1], dict) and call[1].get("limit") == 5
            for call in port.last_page.raw.evaluate_calls
        )

    asyncio.run(_run())


def test_xianyu_detail_mtop() -> None:
    port = _FakePort()
    crawler = create_crawler("xianyu", port)
    mtop_raw = {
        "ret": ["SUCCESS::调用成功"],
        "data": {
            "trackParams": {
                "id": "77",
                "title": "相机",
                "soldPrice": "9",
                "seller_nick": "s",
                "itemStatus": "0",
            }
        },
    }

    async def _run() -> None:
        with patch(
            "src.crawler.sources.xianyu.crawler.Session.from_cookie_header"
        ) as session_factory:
            with patch(
                "src.crawler.sources.xianyu.crawler.mtop_call",
                return_value=mtop_raw,
            ) as mtop:
                result = await crawler.detail(
                    CrawlContext(task_id="t3", meta={"cookie": "unb=1; _m_h5_tk=a_b"}),
                    "77",
                )
        assert len(result.items) == 1
        assert result.items[0].title == "相机"
        session_factory.assert_called_once()
        # mtop 会调详情 + 留言两个 API；断言详情那次
        assert any(
            call.kwargs.get("api", call.args[1] if len(call.args) > 1 else "").endswith(
                ".detail"
            )
            for call in mtop.call_args_list
        )
        assert port.last_page is None

    asyncio.run(_run())


def test_xianyu_detail_falls_back_to_view() -> None:
    view_payload = {
        "item_id": "77",
        "title": "页内相机",
        "price": "¥12",
        "seller_name": "卖家",
        "status": "在售",
    }
    port = _FakePort(views={"77": view_payload})
    crawler = create_crawler("xianyu", port)

    async def _run() -> None:
        with (
            patch(
                "src.crawler.sources.xianyu.crawler.Session.from_cookie_header"
            ),
            patch(
                "src.crawler.sources.xianyu.crawler.mtop_call",
                side_effect=AppError("channel.mtop_failed", "签名失败", status_code=502),
            ),
        ):
            result = await crawler.detail(
                CrawlContext(task_id="t4", meta={"cookie": "unb=1; _m_h5_tk=a_b"}),
                "77",
            )
        assert len(result.items) == 1
        assert result.items[0].title == "页内相机"
        assert result.items[0].raw.get("seller_nick") == "卖家"
        assert port.last_page is not None
        assert port.last_page.closed
        assert port.last_page.goto_calls[0][0] == "https://www.goofish.com/item"
        assert port.last_page.goto_calls[0][1] == {"id": "77"}
        assert any(
            isinstance(call[1], dict) and call[1].get("itemId") == "77"
            for call in port.last_page.raw.evaluate_calls
        )

    asyncio.run(_run())


def test_xiaohongshu_cookie_domain() -> None:
    cookies = cookies_for("xiaohongshu", "a1=token; web_session=sess")
    assert cookies is not None
    by_name = {c.name: c for c in cookies}
    assert by_name["a1"].domain == ".xiaohongshu.com"
    assert by_name["web_session"].domain == ".xiaohongshu.com"


def test_xiaohongshu_search_uses_evaluate() -> None:
    port = _FakePort(
        payload={
            "ready": True,
            "items": [
                {
                    "id": "n1",
                    "noteCard": {
                        "displayTitle": "咖啡",
                        "user": {"nickname": "阿茶"},
                    },
                }
            ],
        }
    )
    crawler = create_crawler("xiaohongshu", port)

    async def _run() -> None:
        result = await crawler.search(
            CrawlContext(task_id="xhs-s", meta={"limit": 5}),
            "咖啡",
        )
        assert len(result.items) == 1
        assert result.items[0].item_id == "n1"
        assert result.items[0].title == "咖啡"
        assert port.last_page is not None
        assert port.last_page.closed
        assert port.last_page.goto_calls[0][0] == "https://www.xiaohongshu.com/search_result"
        assert port.last_page.goto_calls[0][1] == {
            "keyword": "咖啡",
            "source": "web_explore_feed",
        }

    asyncio.run(_run())


def test_xiaohongshu_detail() -> None:
    port = _FakePort(
        payload={
            "ready": True,
            "note": {
                "note": {
                    "noteId": "n1",
                    "title": "笔记标题",
                    "user": {"nickname": "作者"},
                }
            },
        }
    )
    crawler = create_crawler("xiaohongshu", port)

    async def _run() -> None:
        result = await crawler.detail(
            CrawlContext(task_id="xhs-d", meta={"xsec_token": "tok"}),
            "n1",
        )
        assert len(result.items) == 1
        assert result.items[0].title == "笔记标题"
        assert result.items[0].raw.get("seller_nick") == "作者"
        assert port.last_page is not None
        assert port.last_page.closed
        assert port.last_page.goto_calls[0][0] == "https://www.xiaohongshu.com/explore/n1"
        assert port.last_page.goto_calls[0][1] == {
            "xsec_token": "tok",
            "xsec_source": "pc_search",
        }
        assert any(
            isinstance(call[1], dict) and call[1].get("noteId") == "n1"
            for call in port.last_page.raw.evaluate_calls
        )

    asyncio.run(_run())


def test_items_from_payload() -> None:
    items = items_from_payload(
        {
            "items": [
                {"title": "a", "url": "https://www.goofish.com/item?id=9"},
                {"title": "a", "url": "https://www.goofish.com/item?id=9"},
            ]
        }
    )
    assert [i.item_id for i in items] == ["9", "9"]
