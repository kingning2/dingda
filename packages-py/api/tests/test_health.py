from fastapi.testclient import TestClient

from api.app import create_app


def test_health() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["phase"] in {"shell", "warming", "ready"}


def test_runtime_status() -> None:
    client = TestClient(create_app())
    response = client.get("/v1/runtime/status")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["state"] == "running"
    assert isinstance(body["uptime_ms"], int)
