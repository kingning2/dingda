"""健康检查与运行时状态 API 测试。"""

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["phase"] in {"shell", "warming", "ready"}


def test_runtime_status(client: TestClient) -> None:
    response = client.get("/v1/runtime/status")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["state"] == "running"
    assert isinstance(body["uptime_ms"], int)
