"""Channel QR API tests."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.app import create_app
from src.contracts.channel import QrCheckResponse, QrStartResponse


def test_qr_start_and_check_success() -> None:
    app = create_app()
    client = TestClient(app)

    start_payload = QrStartResponse(
        ok=True,
        status="waiting",
        session_id="qr-test",
        qr_base64="ZmFrZQ==",
        detail="请扫码",
    )
    check_payload = QrCheckResponse(
        ok=True,
        status="success",
        session_id="qr-test",
        detail="登录成功！",
        account_id="xy:123",
        display_name="闲鱼账号 123",
        cookie="a=1; b=2",
    )

    with patch("src.api.channel.get_channel_qr_service") as mock_get:
        service = mock_get.return_value
        service.start.return_value = start_payload
        service.check.return_value = check_payload

        start = client.post("/v1/channel/qr/start", json={"platform": "xianyu"})
        assert start.status_code == 200
        assert start.json()["session_id"] == "qr-test"

        check = client.get("/v1/channel/qr/check", params={"session_id": "qr-test"})
        assert check.status_code == 200
        assert check.json()["status"] == "success"
        assert check.json()["account_id"] == "xy:123"
