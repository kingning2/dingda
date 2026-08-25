"""WS 重连与 token 缓存单元测试。"""

from __future__ import annotations

import time
import unittest
from unittest.mock import patch

import crawlers.xianyu.ws.token as token_mod
from crawlers.xianyu.ws.constants import TOKEN_CACHE_TTL_SEC
from crawlers.xianyu.ws.cookies import merge_cookie_header
from crawlers.xianyu.ws.frames import sync_ack_frame
from crawlers.xianyu.ws.token import TokenError, fetch_ws_token


class TestWsReconnectHelpers(unittest.TestCase):
    def test_sync_ack_frame_register_pts(self) -> None:
        frame = sync_ack_frame(pts=1234567890000)
        body = frame["body"][0]
        self.assertEqual(body["pts"], 1234567890000)

    def test_merge_cookie_header_updates_values(self) -> None:
        cookies = [{"name": "unb", "value": "old"}, {"name": "tracknick", "value": "nick"}]
        merged = merge_cookie_header("unb=new; foo=bar", cookies)
        by_name = {item["name"]: item["value"] for item in merged}
        self.assertEqual(by_name["unb"], "new")
        self.assertEqual(by_name["tracknick"], "nick")
        self.assertEqual(by_name["foo"], "bar")

    def test_fetch_ws_token_uses_cache(self) -> None:
        token_mod._token_cache.clear()
        cookies = [{"name": "unb", "value": "u1"}]
        with patch(
            "crawlers.xianyu.ws.token._fetch_ws_token_uncached",
            return_value="tok1",
        ) as mocked:
            first = fetch_ws_token(cookies)
            second = fetch_ws_token(cookies)
        self.assertEqual(first, "tok1")
        self.assertEqual(second, "tok1")
        mocked.assert_called_once()

    def test_fetch_ws_token_cache_expired(self) -> None:
        token_mod._token_cache.clear()
        cookies = [{"name": "unb", "value": "u2"}]
        with patch(
            "crawlers.xianyu.ws.token._fetch_ws_token_uncached",
            side_effect=["tok-a", "tok-b"],
        ):
            first = fetch_ws_token(cookies)
            token_mod._token_cache["u2"] = ("tok-a", time.time() - TOKEN_CACHE_TTL_SEC - 1)
            second = fetch_ws_token(cookies)
        self.assertEqual(first, "tok-a")
        self.assertEqual(second, "tok-b")

    def test_fetch_ws_token_missing_unb(self) -> None:
        with self.assertRaises(TokenError):
            fetch_ws_token([])


if __name__ == "__main__":
    unittest.main()
