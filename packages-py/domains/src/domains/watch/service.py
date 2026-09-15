"""监控目标的增删改查与视图组装。

职责：
    给 HTTP 层提供「加商品进监控、看监控列表、看单条详情、调间隔、移除」，
    并把库里的行组装成前端直接能渲染的视图。

设计说明：
    - 价格涨跌这类展示口径（比首价降了多少、是否处在最低点）在这里算完，
      API 层只做序列化，不重复推导
    - 不轮询、不发请求；取数在 ``poller``，排期在 ``scheduler``
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from contracts.watch import SoldState, WatchState
from domains.watch.insight import WatchChange, derive_changes
from infrastructure.db import watch as watch_repo
from infrastructure.db.watch import WatchPointRow, WatchTargetRow

logger = logging.getLogger("dingda.watch.service")

MIN_INTERVAL_SECONDS = 60
MAX_INTERVAL_SECONDS = 7 * 24 * 3600


@dataclass(frozen=True, slots=True)
class WatchItemInput:
    """加入监控的一条商品。"""

    platform: str
    item_id: str
    title: str = ""
    url: str = ""
    image_url: str | None = None
    account_id: str | None = None


@dataclass(frozen=True, slots=True)
class WatchTargetView:
    """前端直接渲染的监控目标视图。"""

    target_id: str
    platform: str
    item_id: str
    title: str
    url: str
    image_url: str | None
    state: str
    sold_state: str
    first_price: float | None
    last_price: float | None
    min_price: float | None
    max_price: float | None
    price_drop: float | None
    price_drop_ratio: float | None
    last_want_count: str | None
    last_status_text: str | None
    poll_interval_seconds: int
    next_poll_at: float
    last_poll_at: float | None
    last_error: str | None
    fail_count: int
    watched_hours: float
    created_at: float
    updated_at: float


@dataclass(frozen=True, slots=True)
class WatchTargetDetail:
    """单条监控目标：视图 + 价格历史 + 变更事件。"""

    target: WatchTargetView
    points: list[WatchPointRow]
    changes: list[WatchChange]


@dataclass(frozen=True, slots=True)
class WatchSummary:
    """监控概览：回答「多少还在卖、多少卖掉了、多少降价了」。"""

    total: int
    active: int
    paused: int
    archived: int
    on_sale: int
    sold: int
    delisted: int
    gone: int
    unknown: int
    price_dropped: int
    price_risen: int
    awaiting_first_poll: int


def add_targets(
    items: list[WatchItemInput],
    *,
    poll_interval_seconds: int,
) -> list[WatchTargetRow]:
    """批量加入监控；同 (platform, item_id) 幂等，重复加入不重置历史。"""
    interval = clamp_interval(poll_interval_seconds)
    out: list[WatchTargetRow] = []
    for item in items:
        platform = item.platform.strip().lower()
        item_id = item.item_id.strip()
        if not platform or not item_id:
            logger.warning("watch add skipped platform=%s item_id=%s", platform, item_id)
            continue
        out.append(
            watch_repo.upsert_target(
                platform=platform,
                item_id=item_id,
                poll_interval_seconds=interval,
                title=item.title.strip(),
                url=item.url.strip(),
                image_url=item.image_url,
                account_id=item.account_id,
            )
        )
    logger.info("watch add done count=%s interval=%s", len(out), interval)
    return out


def list_views(*, state: str | None = None, limit: int = 200) -> list[WatchTargetView]:
    """列出监控目标视图，按加入时间倒序。"""
    return [build_view(row) for row in watch_repo.list_targets(state=state, limit=limit)]


def get_detail(target_id: str, *, point_limit: int = 500) -> WatchTargetDetail | None:
    """读单条监控目标：视图 + 价格历史点 + 变更事件。"""
    row = watch_repo.get_target(target_id)
    if row is None:
        return None
    points = watch_repo.list_points(target_id=row.target_id, limit=point_limit)
    return WatchTargetDetail(
        target=build_view(row),
        points=points,
        changes=derive_changes(points),
    )


def patch_target(
    target_id: str,
    *,
    state: str | None = None,
    poll_interval_seconds: int | None = None,
) -> WatchTargetRow | None:
    """调整监控状态或轮询间隔；两者都给时先改间隔再切状态。"""
    if watch_repo.get_target(target_id) is None:
        return None
    row: WatchTargetRow | None = None
    if poll_interval_seconds is not None:
        row = watch_repo.set_poll_interval(target_id, clamp_interval(poll_interval_seconds))
    if state is not None:
        row = watch_repo.set_target_state(target_id, state)
    return row if row is not None else watch_repo.get_target(target_id)


def remove_target(target_id: str) -> bool:
    """彻底移除监控目标及其全部价格历史。"""
    return watch_repo.delete_target(target_id)


def summarize() -> WatchSummary:
    """按售出态与价格涨跌统计全部监控目标。"""
    rows = watch_repo.list_targets(state=None, limit=1000)
    counters = {value: 0 for value in SoldState}
    for row in rows:
        counters[row.sold_state] = counters.get(row.sold_state, 0) + 1
    dropped = sum(1 for row in rows if _drop_of(row) is not None and _drop_of(row) > 0)
    risen = sum(1 for row in rows if _drop_of(row) is not None and _drop_of(row) < 0)
    return WatchSummary(
        total=len(rows),
        active=sum(1 for row in rows if row.state == WatchState.ACTIVE),
        paused=sum(1 for row in rows if row.state == WatchState.PAUSED),
        archived=sum(1 for row in rows if row.state == WatchState.ARCHIVED),
        on_sale=counters.get(SoldState.ON_SALE, 0),
        sold=counters.get(SoldState.SOLD, 0),
        delisted=counters.get(SoldState.DELISTED, 0),
        gone=counters.get(SoldState.GONE, 0),
        unknown=counters.get(SoldState.UNKNOWN, 0),
        price_dropped=dropped,
        price_risen=risen,
        awaiting_first_poll=sum(1 for row in rows if row.first_price is None),
    )


def build_view(row: WatchTargetRow) -> WatchTargetView:
    """库行 → 前端视图，顺带算好涨跌口径。"""
    drop = _drop_of(row)
    ratio = (drop / row.first_price) if (drop is not None and row.first_price) else None
    return WatchTargetView(
        target_id=row.target_id,
        platform=row.platform,
        item_id=row.item_id,
        title=row.title,
        url=row.url,
        image_url=row.image_url,
        state=row.state,
        sold_state=row.sold_state,
        first_price=row.first_price,
        last_price=row.last_price,
        min_price=row.min_price,
        max_price=row.max_price,
        price_drop=drop,
        price_drop_ratio=ratio,
        last_want_count=row.last_want_count,
        last_status_text=row.last_status_text,
        poll_interval_seconds=row.poll_interval_seconds,
        next_poll_at=row.next_poll_at,
        last_poll_at=row.last_poll_at,
        last_error=row.last_error,
        fail_count=row.fail_count,
        watched_hours=round((time.time() - row.created_at) / 3600, 1),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def clamp_interval(seconds: int) -> int:
    """把轮询间隔夹到 [1 分钟, 7 天]，防止手滑填出高频或永不再轮询。"""
    try:
        value = int(seconds)
    except (TypeError, ValueError):
        return watch_repo.DEFAULT_POLL_INTERVAL_SECONDS
    return max(MIN_INTERVAL_SECONDS, min(value, MAX_INTERVAL_SECONDS))


def _drop_of(row: WatchTargetRow) -> float | None:
    """相对首价的涨跌额；正数=降价。首价或现价缺失时返回 None。"""
    if row.first_price is None or row.last_price is None:
        return None
    return row.first_price - row.last_price
