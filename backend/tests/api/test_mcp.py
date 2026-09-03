"""MCP HTTP API 测试。"""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.app import create_app


def test_list_mcp_servers() -> None:
    client = TestClient(create_app())
    response = client.get("/v1/mcp/servers")
    assert response.status_code == 200
    payload = response.json()
    assert "servers" in payload
    assert any(item["id"] == "goofish" for item in payload["servers"])
    goofish = next(item for item in payload["servers"] if item["id"] == "goofish")
    assert goofish["command"] == "uv"
    assert "dingda-mcp" in goofish["args"]
