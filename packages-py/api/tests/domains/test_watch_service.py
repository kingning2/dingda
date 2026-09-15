"""商品监控：目标增删改查与视图组装（临时库）。"""

from __future__ import annotations

from pathlib import Path

from contracts.watch import SoldState, WatchState
from domains.watch import service
from infrastructure.db import watch as repo
from infrastructure.db.session import set_db_path


def _add(platform: str = "xianyu", item_id: str = "1001") -> repo.WatchTargetRow:
    """往临时库里加一条监控目标。"""
    return service.add_targets(
        [service.WatchItemInput(platform=platform, item_id=item_id)],
        poll_interval_seconds=21600,
    )[0]


def test_add_targets_is_idempotent_on_platform_and_item(tmp_path: Path) -> None:
    set_db_path(tmp_path / "watch.db")
    first = _add()
    again = _add()
    assert first.target_id == again.target_id
    assert len(service.list_views()) == 1


def test_readd_archived_target_resumes_it(tmp_path: Path) -> None:
    set_db_path(tmp_path / "watch.db")
    row = _add()
    service.patch_target(row.target_id, state=WatchState.ARCHIVED.value)
    assert repo.get_target(row.target_id).state == WatchState.ARCHIVED.value

    resumed = _add()
    assert resumed.target_id == row.target_id
    assert resumed.state == WatchState.ACTIVE.value


def test_add_targets_skips_blank_item_id(tmp_path: Path) -> None:
    set_db_path(tmp_path / "watch.db")
    rows = service.add_targets(
        [service.WatchItemInput(platform="xianyu", item_id="   ")],
        poll_interval_seconds=21600,
    )
    assert rows == []


def test_clamp_interval_keeps_polling_sane() -> None:
    assert service.clamp_interval(1) == service.MIN_INTERVAL_SECONDS
    assert service.clamp_interval(10**9) == service.MAX_INTERVAL_SECONDS
    assert service.clamp_interval(21600) == 21600


def test_build_view_computes_price_drop_from_first_price(tmp_path: Path) -> None:
    set_db_path(tmp_path / "watch.db")
    row = _add()
    repo.save_poll_snapshot(
        target_id=row.target_id,
        sold_state=SoldState.ON_SALE.value,
        price=100.0,
        next_poll_at=0.0,
    )
    repo.save_poll_snapshot(
        target_id=row.target_id,
        sold_state=SoldState.ON_SALE.value,
        price=80.0,
        next_poll_at=0.0,
    )
    view = service.list_views()[0]
    assert view.first_price == 100.0
    assert view.last_price == 80.0
    assert view.min_price == 80.0
    assert view.max_price == 100.0
    assert view.price_drop == 20.0
    assert view.price_drop_ratio == 0.2


def test_build_view_price_drop_is_none_before_first_price(tmp_path: Path) -> None:
    set_db_path(tmp_path / "watch.db")
    _add()
    assert service.list_views()[0].price_drop is None


def test_save_poll_snapshot_backfills_title_once(tmp_path: Path) -> None:
    set_db_path(tmp_path / "watch.db")
    row = _add()
    assert row.title == ""
    repo.save_poll_snapshot(
        target_id=row.target_id,
        sold_state=SoldState.ON_SALE.value,
        price=100.0,
        next_poll_at=0.0,
        title="露营椅",
    )
    assert repo.get_target(row.target_id).title == "露营椅"
    repo.save_poll_snapshot(
        target_id=row.target_id,
        sold_state=SoldState.ON_SALE.value,
        price=90.0,
        next_poll_at=0.0,
        title="卖家改过的标题",
    )
    assert repo.get_target(row.target_id).title == "露营椅"


def test_get_detail_returns_points_and_changes(tmp_path: Path) -> None:
    set_db_path(tmp_path / "watch.db")
    row = _add()
    for price, state in ((100.0, "on_sale"), (88.0, "on_sale"), (88.0, "sold")):
        repo.add_point(target_id=row.target_id, sold_state=state, price=price)
    detail = service.get_detail(row.target_id)
    assert detail is not None
    assert len(detail.points) == 3
    assert [c.kind for c in detail.changes] == ["price_drop", "sold"]


def test_get_detail_returns_none_for_unknown_target(tmp_path: Path) -> None:
    set_db_path(tmp_path / "watch.db")
    assert service.get_detail("watch-missing") is None


def test_patch_target_updates_state_and_interval(tmp_path: Path) -> None:
    set_db_path(tmp_path / "watch.db")
    row = _add()
    updated = service.patch_target(
        row.target_id,
        state=WatchState.PAUSED.value,
        poll_interval_seconds=3600,
    )
    assert updated is not None
    assert updated.state == WatchState.PAUSED.value
    assert updated.poll_interval_seconds == 3600
    assert service.patch_target("watch-missing", state=WatchState.PAUSED.value) is None


def test_summarize_counts_states_and_directions(tmp_path: Path) -> None:
    set_db_path(tmp_path / "watch.db")
    dropped = _add(item_id="1001")
    sold = _add(item_id="1002")
    for target_id, prices in ((dropped.target_id, (100.0, 80.0)), (sold.target_id, (200.0, 200.0))):
        for price in prices:
            repo.save_poll_snapshot(
                target_id=target_id,
                sold_state=SoldState.ON_SALE.value,
                price=price,
                next_poll_at=0.0,
            )
    repo.save_poll_snapshot(
        target_id=sold.target_id,
        sold_state=SoldState.SOLD.value,
        price=200.0,
        next_poll_at=0.0,
    )
    summary = service.summarize()
    assert summary.total == 2
    assert summary.active == 2
    assert summary.sold == 1
    assert summary.price_dropped == 1
    assert summary.price_risen == 0
    assert summary.awaiting_first_poll == 0


def test_remove_target_also_drops_price_history(tmp_path: Path) -> None:
    set_db_path(tmp_path / "watch.db")
    row = _add()
    repo.add_point(target_id=row.target_id, sold_state="on_sale", price=100.0)
    assert service.remove_target(row.target_id) is True
    assert repo.get_target(row.target_id) is None
    assert repo.list_points(target_id=row.target_id) == []
    assert service.remove_target(row.target_id) is False


def test_list_views_filters_by_state(tmp_path: Path) -> None:
    set_db_path(tmp_path / "watch.db")
    kept = _add(item_id="1001")
    paused = _add(item_id="1002")
    service.patch_target(paused.target_id, state=WatchState.PAUSED.value)
    active = service.list_views(state=WatchState.ACTIVE.value)
    assert [v.target_id for v in active] == [kept.target_id]
