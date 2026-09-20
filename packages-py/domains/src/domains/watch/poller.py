"""单条被监控商品的一次轮询。

职责：
    取一次详情、把价格文本收敛成数字、判定售出态，
    再落一个价格历史点并推进目标快照。

设计说明：
    - 取数经 ``ProductFetcher`` 插座，本模块不依赖 agent / crawler
    - 抓取失败不落点（风控、网络抖动不是商品的变化），只累计失败次数；
      但「商品不存在」要落点，因为下架/售出本身就是要观察的信号
    - 不在此处做退避与排队，那是 ``scheduler`` 的事
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from contracts.watch import SoldState
from domains.watch.base import ProductFetcher, ProductSnapshot
from infrastructure.db import accounts as account_repo
from infrastructure.db import watch as watch_repo
from infrastructure.db.watch import WatchTargetRow

logger = logging.getLogger("dingda.watch.poller")

NOT_FOUND_CODE = "crawler.not_found"

_PRICE_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_PRICE_UNITS: tuple[tuple[str, float], ...] = (("亿", 100_000_000.0), ("万", 10_000.0))


@dataclass(frozen=True, slots=True)
class PollOutcome:
    """一次轮询的结果摘要，给调度器决定下一次时间用。"""

    target_id: str
    ok: bool
    price: float | None
    sold_state: str
    error: str | None = None


def parse_price(text: str | None) -> float | None:
    """价格文本 → 数字。``¥1,234.5`` → 1234.5，``¥1.2万`` → 12000.0。

    解析不出或非正数一律返回 ``None``，调用方沿用上一个价格，不要把 0 写进历史。
    """
    if not text:
        return None
    raw = str(text).replace(",", "").replace("，", "").strip()
    match = _PRICE_NUMBER.search(raw)
    if match is None:
        return None
    value = float(match.group(0))
    for unit, factor in _PRICE_UNITS:
        if unit in raw:
            value *= factor
            break
    return value if value > 0 else None


async def poll_target(
    target: WatchTargetRow,
    *,
    fetcher: ProductFetcher,
    next_poll_at: float,
) -> PollOutcome:
    """轮询一条监控商品并落库；返回本次结果供调度器排下一次。"""
    cookie = resolve_target_cookie(target)
    logger.info(
        "watch poll start target_id=%s platform=%s item_id=%s has_cookie=%s",
        target.target_id,
        target.platform,
        target.item_id,
        bool(cookie),
    )
    snapshot = await fetcher(
        platform=target.platform,
        item_id=target.item_id,
        cookie=cookie,
    )
    if snapshot.ok:
        return _record_success(target, snapshot, next_poll_at=next_poll_at)
    if snapshot.error_code == NOT_FOUND_CODE:
        return _record_gone(target, snapshot, next_poll_at=next_poll_at)
    return _record_failure(target, snapshot, next_poll_at=next_poll_at)


def resolve_target_cookie(target: WatchTargetRow) -> str | None:
    """取轮询用的 cookie：优先目标指定账号，否则用该平台第一个登录有效的账号。"""
    if target.account_id:
        row = account_repo.get_account(target.account_id)
        if row is not None and row.cookie.strip():
            return row.cookie
    for row in account_repo.list_accounts(platform=target.platform):
        if row.cookie.strip() and row.auth_valid:
            return row.cookie
    logger.info("watch poll no valid cookie platform=%s", target.platform)
    return None


def _record_success(
    target: WatchTargetRow,
    snapshot: ProductSnapshot,
    *,
    next_poll_at: float,
) -> PollOutcome:
    """抓取成功：落点 + 推进快照。"""
    price = parse_price(snapshot.price_text)
    sold_state = normalize_sold_state(snapshot.sold_state)
    watch_repo.add_point(
        target_id=target.target_id,
        sold_state=sold_state,
        price=price,
        price_text=snapshot.price_text,
        want_count=snapshot.want_count,
        browse_count=snapshot.browse_count,
        status_text=snapshot.status_text,
    )
    watch_repo.save_poll_snapshot(
        target_id=target.target_id,
        sold_state=sold_state,
        price=price,
        next_poll_at=next_poll_at,
        status_text=snapshot.status_text,
        want_count=snapshot.want_count,
        title=snapshot.title,
    )
    logger.info(
        "watch poll done target_id=%s price=%s state=%s",
        target.target_id,
        price,
        sold_state,
    )
    return PollOutcome(
        target_id=target.target_id,
        ok=True,
        price=price,
        sold_state=sold_state,
    )


def _record_gone(
    target: WatchTargetRow,
    snapshot: ProductSnapshot,
    *,
    next_poll_at: float,
) -> PollOutcome:
    """详情已取不到：记为 gone 并落点——这是「卖掉了」的信号，不是失败。"""
    logger.info(
        "watch poll gone target_id=%s message=%s",
        target.target_id,
        snapshot.error_message,
    )
    watch_repo.add_point(
        target_id=target.target_id,
        sold_state=SoldState.GONE,
        status_text=snapshot.error_message,
    )
    watch_repo.save_poll_snapshot(
        target_id=target.target_id,
        sold_state=SoldState.GONE,
        price=None,
        next_poll_at=next_poll_at,
        status_text=snapshot.error_message,
    )
    return PollOutcome(
        target_id=target.target_id,
        ok=True,
        price=None,
        sold_state=SoldState.GONE,
    )


def _record_failure(
    target: WatchTargetRow,
    snapshot: ProductSnapshot,
    *,
    next_poll_at: float,
) -> PollOutcome:
    """风控 / 网络 / 登录失效：不落点，只累计失败并记错误。"""
    error = snapshot.error_message or snapshot.error_code or "未知错误"
    logger.warning(
        "watch poll failed target_id=%s code=%s message=%s",
        target.target_id,
        snapshot.error_code,
        error,
    )
    watch_repo.record_poll_failure(
        target_id=target.target_id,
        error=f"{snapshot.error_code or 'unknown'}: {error}",
        next_poll_at=next_poll_at,
    )
    return PollOutcome(
        target_id=target.target_id,
        ok=False,
        price=None,
        sold_state=target.sold_state,
        error=error,
    )


def normalize_sold_state(value: str | None) -> str:
    """把上游传来的售出态收敛到 ``SoldState``；未知取值按 unknown 处理。"""
    try:
        return SoldState(value or "").value
    except ValueError:
        return SoldState.UNKNOWN.value
