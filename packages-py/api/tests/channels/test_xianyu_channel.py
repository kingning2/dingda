"""闲鱼扫码成功后写昵称头像。"""

from __future__ import annotations

from unittest.mock import patch

from channels.xianyu.channel import XianyuLoginRuntime, XianyuQrChannel


def test_complete_login_uses_page_nav_profile() -> None:
    runtime = XianyuLoginRuntime()
    cookies = {"unb": "1", "_m_h5_tk": "t", "cookie2": "c", "tracknick": "cookie名"}
    with patch(
        "channels.xianyu.channel.fetch_login_profile",
        return_value=("阿闲", "https://img.test/a.png"),
    ) as fetch:
        XianyuQrChannel()._complete_login(runtime, cookies)

    fetch.assert_called_once()
    snap = XianyuQrChannel().snapshot(runtime)
    assert snap.display_name == "阿闲"
    assert snap.avatar_url == "https://img.test/a.png"
    assert snap.account_id == "xy:1"
