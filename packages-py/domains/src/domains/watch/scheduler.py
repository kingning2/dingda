"""监控轮询调度。

职责：
    后台循环把到期的监控目标按各自的间隔均匀铺开轮询，
    失败时退避、商品已结束时降到慢速确认。

设计说明：
    - 串行轮询 + 按活跃数量摊开的间隔，避免集中爆发把账号打到风控
      （活跃 N 条、最小间隔 T 时，两条之间至少等 T/N，夹在 20s ~ 30min）
    - 失败退避按 1×、2×、4×… 间隔翻倍，上限 24 小时
    - 商品售出/下架后不停止轮询，降到 24 小时一次——既省配额，又能捕捉重新上架
    - 新加入的目标 ``next_poll_at`` 即当前时刻，所以加完会立刻排进下一轮，
      用户不用等一个完整间隔才看到首次价格
    - 取数经 ``ProductFetcher`` 插座，由 ``api`` 在挂载时注入
    - 由 ``api.boot.warmup`` 在 ``init_db`` 之后挂上，不挡 /health
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Sequence

from contracts.watch import WatchState, is_finished
from domains.watch.base import ProductFetcher
from domains.watch.poller import PollOutcome, poll_target
from infrastructure.db import watch as watch_repo
from infrastructure.db.watch import WatchTargetRow

logger = logging.getLogger("dingda.watch.scheduler")

POLL_TICK_SECONDS = 60
MAX_TARGETS_PER_ROUND = 25
MIN_GAP_SECONDS = 20.0
MAX_GAP_SECONDS = 1800.0
MANUAL_GAP_SECONDS = 3.0
CONFIRM_INTERVAL_SECONDS = 24 * 3600
MAX_BACKOFF_SECONDS = 24 * 3600
JITTER_RATIO = 0.1

_scheduler_task: asyncio.Task[None] | None = None


async def run_watch_loop(fetcher: ProductFetcher) -> None:
    """调度主循环：每 ``POLL_TICK_SECONDS`` 跑一轮到期目标。"""
    logger.info(
        "监控轮询调度已启动 tick=%ss 每轮上限=%s",
        POLL_TICK_SECONDS,
        MAX_TARGETS_PER_ROUND,
    )
    while True:
        try:
            outcomes = await run_due_round(fetcher)
            if outcomes:
                logger.info(
                    "监控轮次结束 polled=%s ok=%s",
                    len(outcomes),
                    sum(1 for item in outcomes if item.ok),
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("监控轮次异常: %s", exc)
        await asyncio.sleep(POLL_TICK_SECONDS)


async def run_due_round(fetcher: ProductFetcher) -> list[PollOutcome]:
    """轮询一批到期目标，两条之间按活跃数量摊开等待。"""
    due = watch_repo.list_due_targets(now=time.time(), limit=MAX_TARGETS_PER_ROUND)
    if not due:
        return []
    gap = pacing_gap(due)
    logger.info("监控轮次开始 due=%s gap=%.0fs", len(due), gap)
    outcomes: list[PollOutcome] = []
    for index, target in enumerate(due):
        if index:
            await asyncio.sleep(gap)
        outcome = await poll_one(fetcher, target)
        if outcome is not None:
            outcomes.append(outcome)
    return outcomes


async def poll_targets_now(
    fetcher: ProductFetcher,
    *,
    target_ids: Sequence[str] | None = None,
    gap_seconds: float = MANUAL_GAP_SECONDS,
) -> list[PollOutcome]:
    """立刻轮询：给了 ``target_ids`` 就只跑这些，否则跑所有到期的。

    手动触发接口用它；不受每轮上限约束，但仍逐条串行，避免瞬时并发。
    """
    if target_ids:
        targets = [row for row in map(watch_repo.get_target, target_ids) if row is not None]
    else:
        targets = watch_repo.list_due_targets(now=time.time(), limit=MAX_TARGETS_PER_ROUND)
    logger.info("手动轮询开始 targets=%s gap=%.0fs", len(targets), gap_seconds)
    outcomes: list[PollOutcome] = []
    for index, target in enumerate(targets):
        if index:
            await asyncio.sleep(gap_seconds)
        outcome = await poll_one(fetcher, target, force=True)
        if outcome is not None:
            outcomes.append(outcome)
    return outcomes


async def poll_one(
    fetcher: ProductFetcher,
    target: WatchTargetRow,
    *,
    force: bool = False,
) -> PollOutcome | None:
    """轮询一条目标；失败时把下一次时间改成退避值。

    ``force=True`` 用于手动触发：允许轮询已暂停的目标，但不改变其状态。
    """
    fresh = watch_repo.get_target(target.target_id)
    if fresh is None:
        logger.info("监控目标已不存在，跳过 target_id=%s", target.target_id)
        return None
    if fresh.state != WatchState.ACTIVE and not force:
        logger.info("监控目标非活跃，跳过 target_id=%s state=%s", fresh.target_id, fresh.state)
        return None

    success_at = next_success_at(fresh)
    failure_at = next_failure_at(fresh)
    try:
        outcome = await poll_target(fresh, fetcher=fetcher, next_poll_at=success_at)
    except Exception as exc:  # noqa: BLE001
        logger.exception("监控轮询崩溃 target_id=%s", fresh.target_id)
        watch_repo.record_poll_failure(
            target_id=fresh.target_id,
            error=f"poll.crashed: {exc}",
            next_poll_at=failure_at,
        )
        return PollOutcome(
            target_id=fresh.target_id,
            ok=False,
            price=None,
            sold_state=fresh.sold_state,
            error=str(exc),
        )
    if not outcome.ok:
        watch_repo.set_next_poll_at(fresh.target_id, failure_at)
    return outcome


def next_success_at(target: WatchTargetRow, *, now: float | None = None) -> float:
    """成功后的下一次时间：已结束的商品降到慢速确认，其余按间隔 ±10% 抖动。"""
    moment = time.time() if now is None else float(now)
    if is_finished(target.sold_state):
        return moment + CONFIRM_INTERVAL_SECONDS
    jitter = 1.0 + random.uniform(-JITTER_RATIO, JITTER_RATIO)
    return moment + target.poll_interval_seconds * jitter


def next_failure_at(target: WatchTargetRow, *, now: float | None = None) -> float:
    """失败退避：第 n 次失败后退避 ``interval × 2^(n-1)``，上限 24 小时。

    用自增前的 ``fail_count`` 算，所以首次失败只等一个间隔（当作偶发抖动），
    连续失败才逐步翻倍。第二次调用方 ``record_poll_failure`` 时 ``fail_count`` 才 +1。
    """
    moment = time.time() if now is None else float(now)
    exponent = min(max(target.fail_count, 0), 10)
    backoff = min(target.poll_interval_seconds * (2**exponent), MAX_BACKOFF_SECONDS)
    return moment + backoff


def pacing_gap(due: Sequence[WatchTargetRow]) -> float:
    """两条之间的等待：最小间隔 / 活跃条数，夹在 20s ~ 30min。"""
    smallest = min((row.poll_interval_seconds for row in due), default=MIN_GAP_SECONDS)
    active = max(1, watch_repo.count_active())
    return max(MIN_GAP_SECONDS, min(smallest / active, MAX_GAP_SECONDS))


def schedule_watch_scheduler(fetcher: ProductFetcher) -> None:
    """在壳层 bootstrap 预热完成后启动（幂等，不阻塞首屏）。"""
    global _scheduler_task

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("监控调度未挂上：无 running event loop")
        return

    if _scheduler_task is not None and not _scheduler_task.done():
        logger.info("监控调度已在运行，跳过重复挂载")
        return

    _scheduler_task = loop.create_task(run_watch_loop(fetcher), name="dingda-watch")
    logger.info("监控调度任务已创建")
