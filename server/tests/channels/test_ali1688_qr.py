"""1688 clawhub 扫码 Channel / login 原语单测。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.channels.ali1688.channel import Ali1688QrChannel, Ali1688LoginRuntime
from src.channels.ali1688.login import is_plausible_ak
from src.channels.registry import create_qr_login_channel
from src.channels.types import LoginStatus


def test_registry_has_ali1688() -> None:
    channel = create_qr_login_channel("ali1688")
    assert isinstance(channel, Ali1688QrChannel)
    assert channel.platform == "ali1688"


def test_is_plausible_ak() -> None:
    secret = "a" * 32
    raw = secret + "my-ak-id"
    assert is_plausible_ak(raw) is True
    assert is_plausible_ak("short") is False


def test_snapshot_waiting() -> None:
    channel = Ali1688QrChannel()
    runtime = Ali1688LoginRuntime(qr_base64="ZmFrZQ==")
    snap = channel.snapshot(runtime)
    assert snap.status == LoginStatus.WAITING
    assert snap.qr_base64 == "ZmFrZQ=="


def test_snapshot_success() -> None:
    channel = Ali1688QrChannel()
    runtime = Ali1688LoginRuntime(
        qr_base64="ZmFrZQ==",
        cookie="a" * 40,
        account_id="ali1688:id",
        display_name="1688 AK",
    )
    snap = channel.snapshot(runtime)
    assert snap.status == LoginStatus.SUCCESS
    assert snap.cookie == "a" * 40


def test_publish_success_saves_ak(tmp_path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr("src.channels.ali1688.ak.data_dir", lambda: tmp_path)
    import base64

    secret = "c" * 32
    ak_id = "stored-id"
    raw = base64.urlsafe_b64encode(f"{secret}{ak_id}".encode()).decode().rstrip("=")

    channel = Ali1688QrChannel()
    runtime = Ali1688LoginRuntime()
    channel._publish_success(runtime, raw)
    assert runtime.cookie == raw
    assert runtime.account_id == f"ali1688:{ak_id}"
    assert (tmp_path / "ali1688" / "ak.json").exists()


def test_png_looks_like_qr_rejects_blank_and_wide() -> None:
    from io import BytesIO

    from PIL import Image

    from src.channels.ali1688.login import _png_looks_like_qr

    blank = Image.new("RGB", (160, 160), color=(255, 255, 255))
    blank_buf = BytesIO()
    blank.save(blank_buf, format="PNG")
    assert _png_looks_like_qr(blank_buf.getvalue()) is False

    wide = Image.new("RGB", (400, 200), color=(240, 240, 240))
    for x in range(40, 120):
        for y in range(40, 160):
            wide.putpixel((x, y), (0, 0, 0))
    wide_buf = BytesIO()
    wide.save(wide_buf, format="PNG")
    assert _png_looks_like_qr(wide_buf.getvalue()) is False

    # 稀疏面板：大片留白 + 小块码 → 应拒绝
    panel = Image.new("RGB", (300, 350), color=(255, 255, 255))
    for x in range(80, 220):
        for y in range(100, 240):
            if ((x // 6) + (y // 6)) % 2 == 0:
                panel.putpixel((x, y), (0, 0, 0))
    panel_buf = BytesIO()
    panel.save(panel_buf, format="PNG")
    assert _png_looks_like_qr(panel_buf.getvalue()) is False

    qrish = Image.new("RGB", (160, 160), color=(255, 255, 255))
    for x in range(160):
        for y in range(160):
            if (x // 8 + y // 8) % 2 == 0:
                qrish.putpixel((x, y), (0, 0, 0))
    qr_buf = BytesIO()
    qrish.save(qr_buf, format="PNG")
    assert _png_looks_like_qr(qr_buf.getvalue()) is True


def test_qr_service_start_ali1688_no_longer_501() -> None:
    from src.contracts.channel import QrStartRequest
    from src.domains.channel.qr_service import ChannelQrService
    from src.channels.types import LoginSnapshot, LoginStatus

    waiting = LoginSnapshot(
        status=LoginStatus.WAITING,
        qr_base64="ZmFrZQ==",
        qr_url="https://clawhub.1688.com/",
    )
    channel = MagicMock()
    runtime = MagicMock()
    runtime.ready.wait.return_value = True
    channel.start_login.return_value = runtime
    channel.snapshot.return_value = waiting

    with patch(
        "src.domains.channel.qr_service.create_qr_login_channel",
        return_value=channel,
    ):
        service = ChannelQrService()
        result = service.start(QrStartRequest(platform="ali1688"))

    channel.start_login.assert_called_once_with(timeout=180)
    assert result.status == "waiting"
    assert result.qr_base64 == "ZmFrZQ=="
