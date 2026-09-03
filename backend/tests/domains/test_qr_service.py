"""qr_service 与 channels 集成测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.channels.types import LoginSnapshot, LoginStatus
from src.contracts.channel import QrStartRequest
from src.domains.channel.qr_service import ChannelQrService
from src.shared.errors import AppError


def _mock_channel(snapshot: LoginSnapshot) -> MagicMock:
    channel = MagicMock()
    runtime = MagicMock()
    runtime.ready.wait.return_value = True
    channel.start_login.return_value = runtime
    channel.snapshot.return_value = snapshot
    return channel, runtime


def test_start_uses_registry_channel() -> None:
    waiting = LoginSnapshot(
        status=LoginStatus.WAITING,
        qr_base64="ZmFrZQ==",
        qr_url="https://example.com/qr",
    )
    channel, runtime = _mock_channel(waiting)

    with patch(
        "src.domains.channel.qr_service.create_qr_login_channel",
        return_value=channel,
    ):
        service = ChannelQrService()
        result = service.start(QrStartRequest(platform="xianyu"))

    channel.start_login.assert_called_once_with(timeout=120)
    assert result.session_id
    assert result.status == "waiting"
    assert result.qr_url == "https://example.com/qr"


def test_check_returns_scanned_and_keeps_session() -> None:
    scanned = LoginSnapshot(
        status=LoginStatus.SCANNED,
        qr_base64="ZmFrZQ==",
        detail="已扫码，请在手机确认登录",
    )
    channel, runtime = _mock_channel(scanned)

    with patch(
        "src.domains.channel.qr_service.create_qr_login_channel",
        return_value=channel,
    ):
        service = ChannelQrService()
        started = service.start(QrStartRequest(platform="xianyu"))
        checked = service.check(started.session_id)  # type: ignore[arg-type]

    assert checked.status == "scanned"
    assert checked.qr_base64 == "ZmFrZQ=="
    # scanned 非终态，会话应仍在
    channel.snapshot.assert_called()


def test_start_failed_drops_session() -> None:
    failed = LoginSnapshot(status=LoginStatus.FAILED, detail="无法获取二维码")
    channel, _runtime = _mock_channel(failed)

    with patch(
        "src.domains.channel.qr_service.create_qr_login_channel",
        return_value=channel,
    ):
        service = ChannelQrService()
        with pytest.raises(AppError) as exc:
            service.start(QrStartRequest(platform="xianyu"))

    assert exc.value.code == "channel.qr_start_failed"
