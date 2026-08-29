"""小红书 search 适配器单元测试（vendored XhsClient）。

mock `_search_via_xhs_client_sync`，覆盖 Feed→offer 映射、Cookie 校验与异常分支，
不真正启动 Camoufox。"""

from __future__ import annotations

import asyncio
import unittest
from typing import Any
from unittest.mock import patch

from dingda_sidecar.crawlers.vendor.xhs_cli.exceptions import DataFetchError, LoginError
from dingda_sidecar.crawlers.xiaohongshu.search import _feed_to_offer, fetch_search

FEED = {
    "id": "abc123",
    "xsecToken": "tok",
    "modelType": "note",
    "noteCard": {
        "type": "normal",
        "displayTitle": "小红书笔记标题",
        "user": {"nickname": "作者"},
        "interactInfo": {"likedCount": "100"},
        "cover": {"url": "https://img.example.com/cover.jpg"},
    },
}


def _run(
    feeds: Any,
    cookies: list[dict],
    *,
    error: BaseException | None = None,
    headed: bool | None = None,
) -> tuple[dict, dict]:
    calls: dict = {}

    def fake_sync(kw: str, cookie_map: dict, headless: bool) -> Any:
        calls["kw"] = kw
        calls["cookies"] = cookie_map
        calls["headless"] = headless
        if error is not None:
            raise error
        return feeds

    with patch(
        "dingda_sidecar.crawlers.xiaohongshu.search._search_via_xhs_client_sync",
        side_effect=fake_sync,
    ):
        result = asyncio.run(
            fetch_search("防晒霜", account_id="acc", cookies=cookies, max_results=10, headed=headed)
        )
    return result, calls


class TestFeedToOffer(unittest.TestCase):
    def test_maps_feed_to_offer(self) -> None:
        offer = _feed_to_offer(FEED)
        assert offer is not None
        assert offer["offerId"] == "abc123"
        assert offer["title"] == "小红书笔记标题"
        assert offer["supplier"] == "作者"
        assert offer["turnover"] == "100"
        assert offer["image"] == "https://img.example.com/cover.jpg"
        assert offer["url"] == (
            "https://www.xiaohongshu.com/explore/abc123?xsec_token=tok&xsec_source=pc_search"
        )

    def test_drops_invalid(self) -> None:
        assert _feed_to_offer(None) is None
        assert _feed_to_offer({"id": "", "noteCard": {"displayTitle": "x"}}) is None
        assert _feed_to_offer({"id": "1", "noteCard": {}}) is None


class TestFetchSearch(unittest.TestCase):
    def test_happy_path_with_cookies(self) -> None:
        result, calls = _run([FEED], [{"name": "web_session", "value": "s1"}])
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["offers"][0]["offerId"], "abc123")
        self.assertIn("xhs-cli", result["detail"])
        # Cookie 压成 dict 传给 XhsClient
        self.assertEqual(calls["cookies"], {"web_session": "s1"})
        # headed=None → 默认无头
        self.assertIs(calls["headless"], True)

    def test_headed_true_forces_headful(self) -> None:
        _, calls = _run([], [{"name": "web_session", "value": "s1"}], headed=True)
        self.assertIs(calls["headless"], False)

    def test_missing_login_cookie(self) -> None:
        result, calls = _run([], [{"name": "foo", "value": "bar"}])
        self.assertEqual(result["status"], "not_logged_in")
        self.assertIn("web_session", result["detail"])
        # 缺 cookie 时不调用 XhsClient
        self.assertEqual(calls, {})

    def test_empty_feeds(self) -> None:
        result, _ = _run([], [{"name": "web_session", "value": "s1"}])
        self.assertEqual(result["status"], "empty")

    def test_login_error(self) -> None:
        result, _ = _run([], [{"name": "web_session", "value": "s1"}], error=LoginError("会话失效"))
        self.assertEqual(result["status"], "not_logged_in")

    def test_data_fetch_error(self) -> None:
        result, _ = _run(
            [],
            [{"name": "web_session", "value": "s1"}],
            error=DataFetchError("触发风控"),
        )
        self.assertEqual(result["status"], "error")
        self.assertIn("风控", result["detail"])


if __name__ == "__main__":
    unittest.main()
