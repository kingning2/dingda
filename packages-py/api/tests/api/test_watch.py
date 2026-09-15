"""商品监控 HTTP 端点（临时库 + 假取数插头）。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from domains.watch.base import ProductSnapshot
from infrastructure.db.session import set_db_path


def _fetcher(**kwargs: object):
    """造一个固定返回的取数插头。"""

    async def _call(**_ignored: object) -> ProductSnapshot:
        return ProductSnapshot(**kwargs)  # type: ignore[arg-type]

    return _call


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


def test_manual_poll_records_point_and_detail_exposes_history(
    tmp_path: Path,
    client: TestClient,
) -> None:
    set_db_path(tmp_path / "watch.db")
    target = _add(client)["targets"][0]

    with patch("api.watch.fetch_product", new=_fetcher(ok=True, price_text="¥100", sold_state="on_sale")):
        polled = client.post("/v1/watch/poll", json={"target_ids": [target["target_id"]]}).json()
    assert polled["polled"] == 1
    assert polled["succeeded"] == 1
    assert polled["results"][0]["price"] == 100.0

    with patch("api.watch.fetch_product", new=_fetcher(ok=True, price_text="¥80", sold_state="sold")):
        client.post("/v1/watch/poll", json={"target_ids": [target["target_id"]]})

    detail = client.get(f"/v1/watch/targets/{target['target_id']}").json()
    assert [p["price"] for p in detail["points"]] == [100.0, 80.0]
    assert detail["target"]["first_price"] == 100.0
    assert detail["target"]["last_price"] == 80.0
    assert detail["target"]["sold_state"] == "sold"
    assert [c["kind"] for c in detail["changes"]] == ["price_drop", "sold"]


def test_manual_poll_caps_batch_size(tmp_path: Path, client: TestClient) -> None:
    set_db_path(tmp_path / "watch.db")
    ids = [_add(client, str(1000 + index))["targets"][0]["target_id"] for index in range(8)]
    with patch("api.watch.fetch_product", new=_fetcher(ok=True, price_text="¥50")):
        body = client.post("/v1/watch/poll", json={"target_ids": ids}).json()
    assert body["polled"] == 5


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


def test_summary_reports_sold_and_dropped(tmp_path: Path, client: TestClient) -> None:
    set_db_path(tmp_path / "watch.db")
    dropped = _add(client, "1001")["targets"][0]
    sold = _add(client, "1002")["targets"][0]
    with patch("api.watch.fetch_product", new=_fetcher(ok=True, price_text="¥100", sold_state="on_sale")):
        client.post("/v1/watch/poll", json={"target_ids": [dropped["target_id"], sold["target_id"]]})
    with patch("api.watch.fetch_product", new=_fetcher(ok=True, price_text="¥70", sold_state="on_sale")):
        client.post("/v1/watch/poll", json={"target_ids": [dropped["target_id"]]})
    with patch("api.watch.fetch_product", new=_fetcher(ok=True, price_text="¥100", sold_state="sold")):
        client.post("/v1/watch/poll", json={"target_ids": [sold["target_id"]]})

    summary = client.get("/v1/watch/summary").json()
    assert summary["total"] == 2
    assert summary["active"] == 2
    assert summary["sold"] == 1
    assert summary["price_dropped"] == 1
    assert summary["price_risen"] == 0


def test_poll_failure_is_reported_without_adding_point(tmp_path: Path, client: TestClient) -> None:
    set_db_path(tmp_path / "watch.db")
    target = _add(client)["targets"][0]
    with patch(
        "api.watch.fetch_product",
        new=_fetcher(ok=False, error_code="channel.risk", error_message="风控"),
    ):
        body = client.post("/v1/watch/poll", json={"target_ids": [target["target_id"]]}).json()
    assert body["succeeded"] == 0
    assert body["results"][0]["error"] == "风控"
    detail = client.get(f"/v1/watch/targets/{target['target_id']}").json()
    assert detail["points"] == []
    assert detail["target"]["fail_count"] == 1
