"""闲鱼 goofish 搜索适配器单元测试。

mock 替换系统 `browser_page_session`（Camoufox 会话）与 vendored `auto_scroll`，
覆盖 Cookie 注入、三级兜底、headed 解析与各状态分支，不启动真实浏览器。"""

from __future__ import annotations

import asyncio
import unittest
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import patch

from dingda_sidecar.crawlers.goofish.browser.session import prepare_cookies
from dingda_sidecar.crawlers.goofish.search import _item_to_offer, fetch_search
from dingda_sidecar.crawlers.vendor.goofish_cli.core import browser as vg_browser


class _FakePage:
    """记录调用并把固定 payload 返回给 evaluate。"""

    def __init__(self, calls: dict) -> None:
        self._calls = calls
        self.url = "https://www.goofish.com/search"

    async def goto(self, url: str, **kwargs: object) -> None:
        self._calls["url"] = url
        self.url = url

    async def wait_for_timeout(self, ms: int) -> None:
        self._calls["wait_ms"] = ms

    async def evaluate(self, js: str, limit: int) -> Any:
        self._calls["limit"] = limit
        return self._calls["payload"]


class _BrowserRecorder:
    """记录 browser_page_session 收到的参数并 yield 假 Page。"""

    def __init__(self, calls: dict) -> None:
        self._calls = calls

    @asynccontextmanager
    async def browser_page_session(self, *, user_data_dir, headless, platform_name, cookies=None):
        self._calls["headless"] = headless
        self._calls["cookies"] = cookies
        self._calls["platform"] = platform_name
        yield _FakePage(self._calls)

    async def auto_scroll(self, page, times: int = 2, pause_ms: int = 800) -> None:
        self._calls["scrolled"] = times


def _run(
    payload: Any,
    cookies: list[dict],
    *,
    headed: bool | None = None,
    fallback_cookies: list[dict] | None = None,
) -> tuple[dict, dict]:
    calls: dict = {"payload": payload}
    recorder = _BrowserRecorder(calls)

    def resolve_headless(*, headed: bool | None, env_key: str, default_headless: bool) -> bool:
        return (not headed) if headed is not None else default_headless

    with (
        patch(
            "dingda_sidecar.crawlers.goofish.search.browser_page_session",
            recorder.browser_page_session,
        ),
        patch("dingda_sidecar.crawlers.goofish.search.resolve_headless", resolve_headless),
        patch(
            "dingda_sidecar.crawlers.goofish.search._fallback_cookies",
            lambda: fallback_cookies or [],
        ),
        patch.object(vg_browser, "auto_scroll", recorder.auto_scroll),
    ):
        result = asyncio.run(
            fetch_search(
                "iphone",
                account_id="acc1",
                cookies=cookies,
                max_results=10,
                headed=headed,
            )
        )
    return result, calls


class TestItemToOffer(unittest.TestCase):
    def test_maps_card_to_contract(self) -> None:
        item = {
            "title": "iPhone 15 128G 国行",
            "url": "https://www.goofish.com/item?id=7123456789",
            "price": "¥4599",
            "original_price": "¥5999",
            "condition": "95新",
            "brand": "Apple",
            "extra": "电池健康88 | 无拆修",
            "location": "浙江 杭州",
            "badge": "芝麻信用优秀",
        }
        offer = _item_to_offer(item)
        assert offer is not None
        assert offer["itemId"] == "7123456789"
        assert offer["title"] == "iPhone 15 128G 国行"
        assert offer["price"] == "¥4599"
        assert offer["location"] == "浙江 杭州"
        assert offer["tags"] == ["95新", "Apple", "电池健康88", "无拆修", "芝麻信用优秀"]

    def test_drops_invalid_cards(self) -> None:
        assert _item_to_offer({"title": "x"}) is None
        assert _item_to_offer({"title": "x", "url": "https://www.goofish.com/item?foo=1"}) is None
        assert _item_to_offer({"title": "", "url": "https://www.goofish.com/item?id=1"}) is None
        assert _item_to_offer(None) is None


class TestFetchSearch(unittest.TestCase):
    def test_happy_path_with_injected_cookies(self) -> None:
        payload = {
            "items": [
                {"title": "T1", "url": "https://www.goofish.com/item?id=111", "price": "¥10"}
            ],
            "requiresAuth": False,
            "blocked": False,
            "empty": False,
        }
        dingda = [{"name": "unb", "value": "u1"}, {"name": "_m_h5_tk", "value": "t1"}]
        result, calls = _run(payload, dingda, headed=True)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["offers"][0]["itemId"], "111")
        self.assertEqual(result["final_url"], "https://www.goofish.com/search?q=iphone")
        # DingDa 账号库 Cookie → prepare_cookies → 注入浏览器会话
        self.assertEqual(calls["cookies"], prepare_cookies(dingda))
        # headed=True → headless=False
        self.assertIs(calls["headless"], False)
        self.assertEqual(calls["scrolled"], 2)

    def test_empty_cookie_falls_back(self) -> None:
        result, calls = _run({"items": [], "empty": True}, [], fallback_cookies=[])
        # 兜底也拿不到 Cookie → 无 Cookie 启动，交给页面判定登录态
        self.assertIsNone(calls["cookies"])
        self.assertEqual(result["status"], "empty")

    def test_requires_auth_status(self) -> None:
        result, _ = _run({"items": [], "requiresAuth": True}, [])
        self.assertEqual(result["status"], "not_logged_in")

    def test_blocked_status(self) -> None:
        result, _ = _run({"items": [], "blocked": True}, [])
        self.assertEqual(result["status"], "error")

    def test_dom_changed_status(self) -> None:
        result, _ = _run(
            {"items": [], "requiresAuth": False, "blocked": False, "empty": False},
            [{"name": "n", "value": "v"}],
        )
        self.assertEqual(result["status"], "error")
        self.assertIn("DOM 结构已变", result["detail"])

    def test_headed_none_defaults_to_headless(self) -> None:
        result, calls = _run({"items": [], "empty": True}, [], headed=None)
        self.assertEqual(result["status"], "empty")
        self.assertIs(calls["headless"], True)


if __name__ == "__main__":
    unittest.main()
