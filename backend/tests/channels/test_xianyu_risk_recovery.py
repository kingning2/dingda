"""闲鱼扫码风控恢复集成测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.channels.xianyu.channel import XianyuQrChannel, XianyuLoginRuntime


def test_qr_timeout_triggers_risk_recovery() -> None:
    runtime = XianyuLoginRuntime()
    channel = XianyuQrChannel()

    mock_page = MagicMock()
    mock_page.url = "https://www.goofish.com/login"
    mock_page.context.cookies.return_value = [
        {"name": "unb", "value": "123"},
        {"name": "_m_h5_tk", "value": "abc_1"},
        {"name": "cookie2", "value": "c2"},
    ]
    mock_frame = MagicMock()
    mock_frame.query_selector.return_value = None

    with (
        patch(
            "src.channels.xianyu.channel.api.open_login_page",
        ) as open_login,
        patch(
            "src.channels.xianyu.channel.api.capture_qr",
            return_value=("qrpng", "https://qr"),
        ),
        patch(
            "src.channels.xianyu.channel.api.has_login_completed",
            return_value=False,
        ),
        patch(
            "src.channels.xianyu.channel.api.has_all_login_cookies",
            return_value=False,
        ),
        patch(
            "src.channels.xianyu.channel.api.has_scanned_cookies",
            return_value=False,
        ),
        patch(
            "src.channels.xianyu.channel.api.cookie_map",
            return_value={"unb": "123"},
        ),
        patch(
            "src.channels.xianyu.channel.recover_xianyu_login",
            return_value=(
                True,
                "自动滑块通过",
                {"unb": "123", "_m_h5_tk": "t_1", "cookie2": "c2"},
            ),
        ) as recover_mock,
        patch("src.channels.xianyu.channel.time.sleep"),
        patch("src.channels.xianyu.channel.time.monotonic") as monotonic_mock,
    ):
        open_login.return_value.__enter__.return_value = (mock_page, mock_frame)
        monotonic_mock.side_effect = [0, 0, 0, 9999]

        channel._run(runtime, timeout=1)

    recover_mock.assert_called_once()
    snapshot = channel.snapshot(runtime)
    assert snapshot.status.value == "success"
    assert snapshot.account_id == "xy:123"
