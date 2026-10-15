"""Watch 域 HTTP 映射。

职责：
    服务层视图 / 库行 / 领域事件 → 线协议 DTO。模型本体在 ``contracts.watch``，
    本模块只做字段搬运，不定义任何模型。

设计说明：
    - 涨跌口径在 ``domains.watch``，本层只搬运字段
    - 目标不存在时用 ``empty_item`` 占位，让前端拿到稳定响应结构
"""

from __future__ import annotations

from dataclasses import asdict

from contracts.watch import (
    WatchChangeItem,
    WatchDetailResponse,
    WatchPointItem,
    WatchTargetItem,
)
from domains.watch.insight import WatchChange
from domains.watch.service import (
    WatchTargetDetail,
    WatchTargetView,
    build_view,
)
from infrastructure.db.watch import (
    WatchPointRow,
    WatchTargetRow,
)


def to_item(view: WatchTargetView) -> WatchTargetItem:
    """服务层视图 → HTTP DTO。"""
    return WatchTargetItem(**asdict(view))


def to_point(row: WatchPointRow) -> WatchPointItem:
    """价格点行 → HTTP DTO。"""
    data = asdict(row)
    return WatchPointItem(
        observed_at=data["observed_at"],
        price=data["price"],
        price_text=data["price_text"],
        want_count=data["want_count"],
        browse_count=data["browse_count"],
        sold_state=data["sold_state"],
        status_text=data["status_text"],
    )


def to_change(change: WatchChange) -> WatchChangeItem:
    """变更事件 → HTTP DTO。"""
    return WatchChangeItem(**asdict(change))


def detail_response(detail: WatchTargetDetail) -> WatchDetailResponse:
    """服务层详情 → HTTP 响应。"""
    return WatchDetailResponse(
        target=to_item(detail.target),
        points=[to_point(row) for row in detail.points],
        changes=[to_change(change) for change in detail.changes],
    )


def view_of(row: WatchTargetRow) -> WatchTargetView:
    """库行 → 视图（复用服务层的涨跌口径）。"""
    return build_view(row)


def empty_item(target_id: str) -> WatchTargetItem:
    """目标不存在时的占位项，让前端拿到稳定的响应结构。"""
    return WatchTargetItem(
        target_id=target_id,
        platform="",
        item_id="",
        title="",
        url="",
        image_url=None,
        state="",
        sold_state="unknown",
        first_price=None,
        last_price=None,
        min_price=None,
        max_price=None,
        price_drop=None,
        price_drop_ratio=None,
        last_want_count=None,
        last_status_text=None,
        poll_interval_seconds=0,
        next_poll_at=0.0,
        last_poll_at=None,
        last_error=None,
        fail_count=0,
        watched_hours=0.0,
        created_at=0.0,
        updated_at=0.0,
    )
