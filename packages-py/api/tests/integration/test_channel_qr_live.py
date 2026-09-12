"""扫码登录集成测试（需要本机 Chrome + Playwright/Camoufox）。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.app import create_app


@pytest.mark.integration
def test_qr_start_xianyu_returns_qr_image() -> None:
    client = TestClient(create_app())
    response = client.post("/v1/channel/qr/start", json={"platform": "xianyu"})
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["ok"] is True
    assert payload["status"] == "waiting"
    assert payload["session_id"]
    assert payload["qr_base64"]
    assert len(payload["qr_base64"]) > 1000

    check = client.get("/v1/channel/qr/check", params={"session_id": payload["session_id"]})
    assert check.status_code == 200
    checked = check.json()
    assert checked["status"] in {"waiting", "scanned", "success", "failed", "expired"}
    assert checked.get("qr_base64")
