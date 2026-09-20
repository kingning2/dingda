"""商品监控 HTTP 端点（临时库）。"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from infrastructure.db.session import set_db_path


def _add(
    client: TestClient,
    item_id: str = "1001",
    *,
    interval: int | None = None,
    **extra: object,
) -> dict:
    """通过 HTTP 加一条监控目标；``interval`` 是请求体顶层字段，不是 item 字段。"""
    payload: dict = {"items": [{"platform": "xianyu", "item_id": item_id, **extra}]}
    if interval is not None:
        payload["poll_interval_seconds"] = interval
    response = client.post("/v1/watch/targets", json=payload)
    assert response.status_code == 200
    return response.json()


def test_add_targets_returns_view_with_defaults(tmp_path: Path, client: TestClient) -> None:
    set_db_path(tmp_path / "watch.db")
    body = _add(client, interval=21600)
    assert body["ok"] is True
    assert body["added"] == 1
    target = body["targets"][0]
    assert target["item_id"] == "1001"
    assert target["state"] == "active"
    assert target["sold_state"] == "unknown"
    assert target["poll_interval_seconds"] == 21600
    assert target["first_price"] is None
    assert target["price_drop"] is None


def test_add_targets_is_idempotent(tmp_path: Path, client: TestClient) -> None:
    set_db_path(tmp_path / "watch.db")
    first = _add(client)
    second = _add(client)
    assert first["targets"][0]["target_id"] == second["targets"][0]["target_id"]
    assert client.get("/v1/watch/targets").json()["total"] == 1


def test_add_targets_rejects_empty_items(tmp_path: Path, client: TestClient) -> None:
    set_db_path(tmp_path / "watch.db")
    assert client.post("/v1/watch/targets", json={"items": []}).status_code == 422


def test_add_targets_clamps_interval(tmp_path: Path, client: TestClient) -> None:
    set_db_path(tmp_path / "watch.db")
    body = _add(client, interval=1)
    assert body["targets"][0]["poll_interval_seconds"] == 60


def test_list_targets_filters_by_state(tmp_path: Path, client: TestClient) -> None:
    set_db_path(tmp_path / "watch.db")
    _add(client, "1001")
    paused = _add(client, "1002")["targets"][0]
    client.patch(f"/v1/watch/targets/{paused['target_id']}", json={"state": "paused"})

    active = client.get("/v1/watch/targets", params={"state": "active"}).json()
    assert [t["item_id"] for t in active["targets"]] == ["1001"]
    assert client.get("/v1/watch/targets").json()["total"] == 2


def test_list_targets_rejects_unknown_state(tmp_path: Path, client: TestClient) -> None:
    set_db_path(tmp_path / "watch.db")
    assert client.get("/v1/watch/targets", params={"state": "bogus"}).status_code == 422


def test_detail_reports_missing_target_without_500(tmp_path: Path, client: TestClient) -> None:
    set_db_path(tmp_path / "watch.db")
    body = client.get("/v1/watch/targets/watch-missing").json()
    assert body["ok"] is False
    assert body["points"] == []


def test_patch_target_updates_state_and_interval(tmp_path: Path, client: TestClient) -> None:
    set_db_path(tmp_path / "watch.db")
    target = _add(client)["targets"][0]
    body = client.patch(
        f"/v1/watch/targets/{target['target_id']}",
        json={"state": "paused", "poll_interval_seconds": 3600},
    ).json()
    assert body["ok"] is True
    assert body["target"]["state"] == "paused"
    assert body["target"]["poll_interval_seconds"] == 3600


def test_patch_rejects_interval_below_minimum(tmp_path: Path, client: TestClient) -> None:
    set_db_path(tmp_path / "watch.db")
    target = _add(client)["targets"][0]
    response = client.patch(
        f"/v1/watch/targets/{target['target_id']}",
        json={"poll_interval_seconds": 5},
    )
    assert response.status_code == 422


def test_delete_target_removes_it(tmp_path: Path, client: TestClient) -> None:
    set_db_path(tmp_path / "watch.db")
    target = _add(client)["targets"][0]
    body = client.delete(f"/v1/watch/targets/{target['target_id']}").json()
    assert body == {"ok": True, "removed": True}
    assert client.get("/v1/watch/targets").json()["total"] == 0
    assert client.delete("/v1/watch/targets/watch-missing").json()["ok"] is False


def test_summary_of_empty_watchlist(tmp_path: Path, client: TestClient) -> None:
    set_db_path(tmp_path / "watch.db")
    _add(client, "1001")
    _add(client, "1002")

    summary = client.get("/v1/watch/summary").json()
    assert summary["total"] == 2
    assert summary["active"] == 2
    assert summary["sold"] == 0
    assert summary["price_dropped"] == 0
    assert summary["awaiting_first_poll"] == 2
