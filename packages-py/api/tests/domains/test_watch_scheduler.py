"""商品监控：轮询调度、退避与落点纪律（临时库 + 假取数插头）。"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from unittest.mock import patch

from contracts.watch import SoldState, WatchState
from domains.watch import scheduler, service
from domains.watch.base import ProductSnapshot
from infrastructure.db import watch as repo
from infrastructure.db.session import set_db_path


def _fetcher(**kwargs: object):
    """造一个固定返回的取数插头。"""

    async def _call(**_ignored: object) -> ProductSnapshot:
        return ProductSnapshot(**kwargs)  # type: ignore[arg-type]

    return _call


def _add(item_id: str = "1001", interval: int = 21600) -> repo.WatchTargetRow:
    """加一条监控目标并让它立刻到期。"""
    row = service.add_targets(
        [service.WatchItemInput(platform="xianyu", item_id=item_id)],
        poll_interval_seconds=interval,
    )[0]
    repo.set_next_poll_at(row.target_id, time.time() - 1)
    return repo.get_target(row.target_id)  # type: ignore[return-value]


def test_run_due_round_polls_and_records_point(tmp_path: Path) -> None:
    set_db_path(tmp_path / "watch.db")
    row = _add()
    outcomes = asyncio.run(
        scheduler.run_due_round(_fetcher(ok=True, price_text="¥88", sold_state="on_sale"))
    )
    assert [o.ok for o in outcomes] == [True]
    points = repo.list_points(target_id=row.target_id)
    assert [(p.price, p.sold_state) for p in points] == [(88.0, "on_sale")]
    assert repo.get_target(row.target_id).fail_count == 0


def test_new_target_is_due_immediately(tmp_path: Path) -> None:
    """新加入的目标立刻到期，用户不必等一个完整间隔才看到首次价格。"""
    set_db_path(tmp_path / "watch.db")
    row = service.add_targets(
        [service.WatchItemInput(platform="xianyu", item_id="1001")],
        poll_interval_seconds=21600,
    )[0]
    assert row.next_poll_at <= time.time()
    outcomes = asyncio.run(scheduler.run_due_round(_fetcher(ok=True, price_text="¥88")))
    assert [o.target_id for o in outcomes] == [row.target_id]


def test_run_due_round_ignores_targets_not_yet_due(tmp_path: Path) -> None:
    set_db_path(tmp_path / "watch.db")
    row = service.add_targets(
        [service.WatchItemInput(platform="xianyu", item_id="1001")],
        poll_interval_seconds=21600,
    )[0]
    repo.set_next_poll_at(row.target_id, time.time() + 3600)
    assert asyncio.run(scheduler.run_due_round(_fetcher(ok=True, price_text="¥88"))) == []


def test_run_due_round_skips_non_active_targets(tmp_path: Path) -> None:
    set_db_path(tmp_path / "watch.db")
    row = _add()
    service.patch_target(row.target_id, state=WatchState.PAUSED.value)
    repo.set_next_poll_at(row.target_id, time.time() - 1)
    assert asyncio.run(scheduler.run_due_round(_fetcher(ok=True, price_text="¥88"))) == []
    assert repo.list_points(target_id=row.target_id) == []


def test_failed_poll_records_no_point_and_backs_off(tmp_path: Path) -> None:
    set_db_path(tmp_path / "watch.db")
    row = _add()
    outcomes = asyncio.run(
        scheduler.run_due_round(
            _fetcher(ok=False, error_code="channel.risk", error_message="风控")
        )
    )
    assert [o.ok for o in outcomes] == [False]
    assert repo.list_points(target_id=row.target_id) == []
    fresh = repo.get_target(row.target_id)
    assert fresh.fail_count == 1
    assert "channel.risk" in (fresh.last_error or "")
    # 首次失败退避一个间隔（21600s），晚于成功路径的 ±10% 抖动区间
    assert fresh.next_poll_at - time.time() > 21000


def test_not_found_records_gone_point_instead_of_failure(tmp_path: Path) -> None:
    set_db_path(tmp_path / "watch.db")
    row = _add()
    outcomes = asyncio.run(
        scheduler.run_due_round(
            _fetcher(ok=False, error_code="crawler.not_found", error_message="未找到商品")
        )
    )
    assert [o.ok for o in outcomes] == [True]
    points = repo.list_points(target_id=row.target_id)
    assert [p.sold_state for p in points] == [SoldState.GONE.value]
    fresh = repo.get_target(row.target_id)
    assert fresh.sold_state == SoldState.GONE.value
    assert fresh.fail_count == 0


def test_fetcher_crash_is_recorded_as_failure(tmp_path: Path) -> None:
    set_db_path(tmp_path / "watch.db")
    row = _add()

    async def _boom(**_ignored: object) -> ProductSnapshot:
        raise RuntimeError("network down")

    outcomes = asyncio.run(scheduler.run_due_round(_boom))
    assert [o.ok for o in outcomes] == [False]
    assert repo.get_target(row.target_id).fail_count == 1
    assert repo.list_points(target_id=row.target_id) == []


def test_poll_targets_now_forces_paused_target(tmp_path: Path) -> None:
    set_db_path(tmp_path / "watch.db")
    row = _add()
    service.patch_target(row.target_id, state=WatchState.PAUSED.value)
    outcomes = asyncio.run(
        scheduler.poll_targets_now(
            _fetcher(ok=True, price_text="¥77", sold_state="on_sale"),
            target_ids=[row.target_id],
            gap_seconds=0.0,
        )
    )
    assert [o.ok for o in outcomes] == [True]
    assert repo.list_points(target_id=row.target_id)[0].price == 77.0
    # 手动触发不改变暂停状态
    assert repo.get_target(row.target_id).state == WatchState.PAUSED.value


def test_poll_targets_now_ignores_unknown_target_id(tmp_path: Path) -> None:
    set_db_path(tmp_path / "watch.db")
    outcomes = asyncio.run(
        scheduler.poll_targets_now(_fetcher(ok=True), target_ids=["watch-missing"], gap_seconds=0.0)
    )
    assert outcomes == []


def test_next_success_at_jitters_around_interval(tmp_path: Path) -> None:
    set_db_path(tmp_path / "watch.db")
    row = _add(interval=21600)
    delta = scheduler.next_success_at(row) - time.time()
    assert 21600 * 0.9 <= delta <= 21600 * 1.1


def test_next_success_at_slows_down_after_finished(tmp_path: Path) -> None:
    set_db_path(tmp_path / "watch.db")
    row = _add()
    sold = repo.save_poll_snapshot(
        target_id=row.target_id,
        sold_state=SoldState.SOLD.value,
        price=88.0,
        next_poll_at=0.0,
    )
    assert sold is not None
    delta = scheduler.next_success_at(sold) - time.time()
    assert abs(delta - scheduler.CONFIRM_INTERVAL_SECONDS) < 5


def test_next_failure_at_backs_off_exponentially_and_caps(tmp_path: Path) -> None:
    set_db_path(tmp_path / "watch.db")
    row = _add(interval=3600)
    assert abs(scheduler.next_failure_at(row) - time.time() - 3600) < 5
    for _ in range(3):
        repo.record_poll_failure(target_id=row.target_id, error="x", next_poll_at=0.0)
    grown = repo.get_target(row.target_id)
    assert grown is not None
    assert abs(scheduler.next_failure_at(grown) - time.time() - 3600 * 8) < 5

    for _ in range(8):
        repo.record_poll_failure(target_id=row.target_id, error="x", next_poll_at=0.0)
    capped = repo.get_target(row.target_id)
    assert capped is not None
    assert abs(scheduler.next_failure_at(capped) - time.time() - scheduler.MAX_BACKOFF_SECONDS) < 5


def test_pacing_gap_spreads_requests_across_active_targets(tmp_path: Path) -> None:
    set_db_path(tmp_path / "watch.db")
    rows = [_add(item_id=str(1000 + index), interval=3600) for index in range(4)]
    gap = scheduler.pacing_gap(rows)
    assert gap == 3600 / 4
    assert scheduler.pacing_gap([]) == scheduler.MIN_GAP_SECONDS


def test_pacing_gap_is_clamped_to_upper_bound(tmp_path: Path) -> None:
    set_db_path(tmp_path / "watch.db")
    row = _add(interval=service.MAX_INTERVAL_SECONDS)
    assert scheduler.pacing_gap([row]) == scheduler.MAX_GAP_SECONDS


def test_schedule_watch_scheduler_is_idempotent_and_polls(tmp_path: Path) -> None:
    """挂载点：调度任务真的跑起来、重复挂载不叠加、能落点。

    这是 ``api.boot.warmup`` 接线的唯一保证——挂错了后台就永远不会轮询。
    """
    set_db_path(tmp_path / "watch.db")
    row = _add()

    async def _run() -> None:
        scheduler._scheduler_task = None
        try:
            with patch.object(scheduler, "POLL_TICK_SECONDS", 0.05):
                scheduler.schedule_watch_scheduler(_fetcher(ok=True, price_text="¥88"))
                mounted = scheduler._scheduler_task
                assert mounted is not None

                scheduler.schedule_watch_scheduler(_fetcher(ok=True, price_text="¥99"))
                assert scheduler._scheduler_task is mounted

                await asyncio.sleep(0.2)
                mounted.cancel()
                try:
                    await mounted
                except asyncio.CancelledError:
                    pass
        finally:
            scheduler._scheduler_task = None

    asyncio.run(_run())
    points = repo.list_points(target_id=row.target_id)
    assert [p.price for p in points] == [88.0]
