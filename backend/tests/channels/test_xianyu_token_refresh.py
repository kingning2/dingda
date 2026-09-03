"""闲鱼 token 刷新单元测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.channels.xianyu.token_refresh import refresh_token


class TestXianyuTokenRefresh:
    def test_missing_cookie_keys(self) -> None:
        with patch("src.channels.xianyu.token_refresh.is_vendor_installed", return_value=True):
            cookie, ok = refresh_token("unb=1")
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
            patch("src.channels.xianyu.token_refresh.is_vendor_installed", return_value=True),
            patch("src.channels.xianyu.token_refresh.get_goofish_session_factory") as factory,
            patch("src.channels.xianyu.token_refresh._ping_login"),
            patch("src.channels.xianyu.token_refresh._device_id", return_value="dev"),
        ):
            factory.return_value.Session.return_value = session
            cookie, ok = refresh_token("unb=123; _m_h5_tk=old; cookie2=c")

        assert ok is True
        assert "_m_h5_tk=new_token" in cookie

    def test_fallback_to_camoufox(self) -> None:
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
            patch("src.channels.xianyu.token_refresh.is_vendor_installed", return_value=True),
            patch("src.channels.xianyu.token_refresh.get_goofish_session_factory") as factory,
            patch(
                "src.channels.xianyu.token_refresh._ping_login",
                side_effect=ping_side_effect,
            ),
            patch(
                "src.channels.xianyu.token_refresh.refresh_xianyu_cookies",
                return_value={
                    "unb": "123",
                    "_m_h5_tk": "from_camoufox",
                    "cookie2": "c",
                },
            ),
            patch("src.channels.xianyu.token_refresh._device_id", return_value="dev"),
        ):
            factory.return_value.Session.return_value = session
            cookie, ok = refresh_token("unb=123; _m_h5_tk=old; cookie2=c")

        assert ok is True
        assert "_m_h5_tk=from_camoufox" in cookie
