"""小红书 Cookie 注入域名。"""

from __future__ import annotations

from src.browser.context import cookies_to_playwright
from src.channels.xiaohongshu.cookies import cookie_map, to_browser_cookies


def test_to_browser_cookies_has_domain() -> None:
    cookies = to_browser_cookies({"a1": "token", "web_session": "sess", "empty": ""})
    by_name = {c.name: c for c in cookies}
    assert by_name["a1"].domain == ".xiaohongshu.com"
    assert by_name["web_session"].domain == ".xiaohongshu.com"
    assert "empty" not in by_name
    payload = cookies_to_playwright(cookies)
    assert all("domain" in item for item in payload)


def test_cookie_map_from_dicts() -> None:
    assert cookie_map([{"name": "a", "value": "1"}, {"name": "b", "value": ""}]) == {"a": "1"}
