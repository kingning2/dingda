"""商品监控结论推导。

职责：
    把 ``watch_points`` 的时间序列收敛成用户真正要看的两件事：
    价格怎么变、商品什么时候卖掉了。

设计说明：
    - 只读点序列，不碰数据库、不发请求；入参出参都是纯数据，便于单测
    - 相邻两点比一次，所以首点不产生事件（首价看 ``watch_targets.first_price``）
    - 售出/下架只在状态真正翻转时记一次，避免每个点都刷同一条
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from contracts.watch import SoldState
from infrastructure.db.watch import WatchPointRow

KIND_PRICE_DROP = "price_drop"
KIND_PRICE_RISE = "price_rise"
KIND_SOLD = "sold"
KIND_DELISTED = "delisted"
KIND_GONE = "gone"
KIND_RELISTED = "relisted"

_STATE_LABEL = {
    SoldState.SOLD: "已售出",
    SoldState.DELISTED: "已下架",
    SoldState.GONE: "详情已取不到（通常已售出或删除）",
    SoldState.ON_SALE: "重新在售",
}


@dataclass(frozen=True, slots=True)
class WatchChange:
    """一次值得告诉用户的变更。"""

    kind: str
    observed_at: float
    from_price: float | None
    to_price: float | None
    delta: float | None
    delta_ratio: float | None
    message: str


def derive_changes(points: Sequence[WatchPointRow]) -> list[WatchChange]:
    """按时间正序比对相邻观测点，产出降价 / 涨价 / 售出 / 下架 / 重新在售事件。"""
    out: list[WatchChange] = []
    for prev, curr in zip(points, points[1:]):
        out.extend(_price_change(prev, curr))
        out.extend(_state_change(prev, curr))
    return out


def _price_change(prev: WatchPointRow, curr: WatchPointRow) -> list[WatchChange]:
    """价格数字变化 → 降价或涨价事件；任一端缺价格则跳过。"""
    if prev.price is None or curr.price is None or prev.price == curr.price:
        return []
    delta = curr.price - prev.price
    ratio = (delta / prev.price) if prev.price else None
    kind = KIND_PRICE_DROP if delta < 0 else KIND_PRICE_RISE
    verb = "降价" if delta < 0 else "涨价"
    percent = f"（{abs(ratio) * 100:.1f}%）" if ratio is not None else ""
    return [
        WatchChange(
            kind=kind,
            observed_at=curr.observed_at,
            from_price=prev.price,
            to_price=curr.price,
            delta=delta,
            delta_ratio=ratio,
            message=f"{verb} ¥{abs(delta):.2f}{percent}：¥{prev.price:.2f} → ¥{curr.price:.2f}",
        )
    ]


def _state_change(prev: WatchPointRow, curr: WatchPointRow) -> list[WatchChange]:
    """售出态翻转 → 对应事件；从已结束态回到在售记为重新在售。"""
    if prev.sold_state == curr.sold_state:
        return []
    label = _STATE_LABEL.get(curr.sold_state)
    if label is None:
        return []
    return [
        WatchChange(
            kind=_kind_for(curr.sold_state),
            observed_at=curr.observed_at,
            from_price=prev.price,
            to_price=curr.price,
            delta=None,
            delta_ratio=None,
            message=label,
        )
    ]


def _kind_for(sold_state: str) -> str:
    if sold_state == SoldState.SOLD:
        return KIND_SOLD
    if sold_state == SoldState.DELISTED:
        return KIND_DELISTED
    if sold_state == SoldState.GONE:
        return KIND_GONE
    return KIND_RELISTED
