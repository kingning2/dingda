"""Watch 域 DTO 与映射。

职责：
    watch 域的请求 / 响应 Pydantic 模型，以及服务层视图 → HTTP DTO 的映射。

设计说明：
    - 涨跌口径在 ``domains.watch``，本层只搬运字段
    - 目标不存在时用 ``empty_item`` 占位，让前端拿到稳定响应结构
"""

from __future__ import annotations

from dataclasses import asdict

from pydantic import BaseModel, Field

from contracts.watch import WatchState
from domains.watch.insight import WatchChange
from domains.watch.service import (
    WatchTargetDetail,
    WatchTargetView,
    build_view,
)
from infrastructure.db.watch import (
    DEFAULT_POLL_INTERVAL_SECONDS,
    WatchPointRow,
    WatchTargetRow,
)

MANUAL_POLL_MAX = 5


class WatchTargetInput(BaseModel):
    """加入监控的一条商品。"""

    platform: str = Field(description="xianyu / xiaohongshu")
    item_id: str = Field(description="来自搜品结果的商品 id")
    title: str = Field(default="", description="可选；不传则首次轮询后自动补上")
    url: str = Field(default="", description="可选商品链接")
    image_url: str | None = Field(default=None, description="可选封面图")
    account_id: str | None = Field(default=None, description="可选；绑定某个账号轮询")


class WatchAddRequest(BaseModel):
    """批量加入监控。"""

    items: list[WatchTargetInput] = Field(min_length=1, description="要监控的商品")
    poll_interval_seconds: int = Field(
        default=DEFAULT_POLL_INTERVAL_SECONDS,
        description="单条商品的轮询间隔，默认 6 小时；夹在 60 ~ 604800 秒",
    )


class WatchTargetItem(BaseModel):
    """前端直接渲染的监控目标。"""

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
    price_drop: float | None = Field(description="首价 − 现价；正数表示已降价")
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


class WatchPointItem(BaseModel):
    """价格历史上的一个观测点。"""

    observed_at: float
    price: float | None
    price_text: str | None
    want_count: str | None
    browse_count: str | None
    sold_state: str
    status_text: str | None


class WatchChangeItem(BaseModel):
    """一次值得关注的变更。"""

    kind: str = Field(description="price_drop / price_rise / sold / delisted / gone / relisted")
    observed_at: float
    from_price: float | None
    to_price: float | None
    delta: float | None
    delta_ratio: float | None
    message: str


class WatchAddResponse(BaseModel):
    """加入监控结果。"""

    ok: bool = True
    added: int
    targets: list[WatchTargetItem]


class WatchListResponse(BaseModel):
    """监控列表。"""

    ok: bool = True
    total: int
    targets: list[WatchTargetItem]


class WatchDetailResponse(BaseModel):
    """单条监控详情。"""

    ok: bool = True
    target: WatchTargetItem
    points: list[WatchPointItem]
    changes: list[WatchChangeItem]


class WatchPatchRequest(BaseModel):
    """调整监控状态或间隔。"""

    state: WatchState | None = Field(default=None, description="active / paused / archived")
    poll_interval_seconds: int | None = Field(default=None, ge=60, le=604800)


class WatchDeleteResponse(BaseModel):
    """移除监控结果。"""

    ok: bool
    removed: bool


class WatchSummaryResponse(BaseModel):
    """监控概览。"""

    ok: bool = True
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


class WatchPollRequest(BaseModel):
    """手动触发一次轮询。"""

    target_ids: list[str] | None = Field(
        default=None,
        description=f"只轮询这些目标；不传则轮询所有到期的。最多 {MANUAL_POLL_MAX} 条",
    )


class WatchPollResult(BaseModel):
    """单条轮询结果。"""

    target_id: str
    ok: bool
    price: float | None
    sold_state: str
    error: str | None


class WatchPollResponse(BaseModel):
    """手动轮询结果。"""

    ok: bool = True
    polled: int
    succeeded: int
    results: list[WatchPollResult]


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
