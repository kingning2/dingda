"""登录迁移相关：闲鱼 Cookie 域名与 browser.sync 契约。"""

from __future__ import annotations

from src.browser.context import cookies_to_playwright
from src.channels.xianyu.cookies import cookie_domain, cookie_map, to_browser_cookies


def test_xianyu_cookie_domain() -> None:
    assert cookie_domain("_m_h5_tk") == ".taobao.com"
    assert cookie_domain("unb") == ".goofish.com"


def test_to_browser_cookies_has_domains() -> None:
    cookies = to_browser_cookies({"_m_h5_tk": "a", "unb": "1", "empty": ""})
    by_name = {c.name: c for c in cookies}
    assert by_name["_m_h5_tk"].domain == ".taobao.com"
    assert by_name["unb"].domain == ".goofish.com"
    assert "empty" not in by_name
    payload = cookies_to_playwright(cookies)
    assert all("domain" in item for item in payload)


def test_cookie_map_from_dicts() -> None:
    assert cookie_map([{"name": "a", "value": "1"}, {"name": "b", "value": ""}]) == {"a": "1"}
