"""闲鱼 refresh 单测（mock mtop / session）。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.channels.xianyu.refresh import _profile_from_nav, token


class TestRefreshToken:
    def test_missing_cookie_keys(self) -> None:
        cookie, ok = token("unb=1")
        assert ok is False
        assert cookie == "unb=1"

    def test_refresh_success(self) -> None:
        session = MagicMock()
        session.http.cookies.get_dict.return_value = {
            "unb": "123",
            "_m_h5_tk": "new_token",
            "cookie2": "c",
        }
        session.unb = "123"

        with (
            patch(
                "src.channels.xianyu.refresh.Session.from_cookie_header",
                return_value=session,
            ),
            patch("src.channels.xianyu.refresh._ping_login"),
        ):
            cookie, ok = token("unb=123; _m_h5_tk=old; cookie2=c")

        assert ok is True
        assert "_m_h5_tk=new_token" in cookie

    def test_fallback_to_browser(self) -> None:
        session = MagicMock()
        session.http.cookies.get_dict.return_value = {
            "unb": "123",
            "_m_h5_tk": "from_camoufox",
            "cookie2": "c",
        }
        session.unb = "123"

        def ping_side_effect(sess, *, auto_refresh=False):
            if ping_side_effect.calls == 0:
                ping_side_effect.calls += 1
                raise RuntimeError("token expired")
            return None

        ping_side_effect.calls = 0

        with (
            patch(
                "src.channels.xianyu.refresh.Session.from_cookie_header",
                return_value=session,
            ),
            patch(
                "src.channels.xianyu.refresh._ping_login",
                side_effect=ping_side_effect,
            ),
            patch(
                "src.channels.xianyu.refresh.refresh",
                return_value={
                    "unb": "123",
                    "_m_h5_tk": "from_camoufox",
                    "cookie2": "c",
                },
            ),
        ):
            cookie, ok = token("unb=123; _m_h5_tk=old; cookie2=c")

        assert ok is True
        assert "_m_h5_tk=from_camoufox" in cookie
        session.sync_cookies.assert_called_once()


def test_profile_from_nav() -> None:
    page = _profile_from_nav(
        {
            "data": {
                "module": {
                    "base": {
                        "displayName": "阿闲",
                        "avatar": "https://img.goofish.com/a.png",
                        "followers": "3",
                        "following": "1",
                        "soldCount": 0,
                        "purchaseCount": 2,
                        "collectionCount": 28,
                    }
                }
            }
        }
    )
    assert page.display_name == "阿闲"
    assert page.avatar_url == "https://img.goofish.com/a.png"
    assert page.followers == 3
    assert page.following == 1
    assert page.sold_count == 0
    assert page.purchase_count == 2
    assert page.collection_count == 28


def test_profile_calls_page_nav() -> None:
    session = MagicMock()
    raw = {
        "ret": ["SUCCESS::调用成功"],
        "data": {
            "module": {
                "base": {
                    "displayName": "阿闲",
                    "avatar": "https://img.goofish.com/a.png",
                }
            }
        },
    }
    with (
        patch(
            "src.channels.xianyu.refresh.Session.from_cookie_header",
            return_value=session,
        ),
        patch("src.channels.xianyu.refresh.mtop_call", return_value=raw) as mtop,
    ):
        from src.channels.xianyu.refresh import profile

        name, avatar = profile("unb=1; _m_h5_tk=a_b; cookie2=c")

    assert name == "阿闲"
    assert avatar == "https://img.goofish.com/a.png"
    mtop.assert_called_once()
    assert mtop.call_args.kwargs["api"] == "mtop.idle.web.user.page.nav"
    assert mtop.call_args.kwargs["data"] == {}
