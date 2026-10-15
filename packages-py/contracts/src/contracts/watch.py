"""商品监控共享契约。

职责：
    watch 域的两层契约：
    1. 状态词表——商品售出态 ``SoldState`` 与监控开关态 ``WatchState``，
       值即落库值，采集端与业务端共用；
    2. 线协议模型——``/v1/watch/*`` 全部 HTTP 请求 / 响应的 Pydantic DTO，
       api 层直接复用，不再各写一套。

设计说明：
    - crawler 产出售出态、tools 透传、domains.watch 消费，三包都依赖 contracts，
      所以词表放这里，避免各方各写一套字符串
    - 词表的值即落库值（``watch_targets.state`` / ``sold_state``）。改值等于改数据，
      必须配迁移，不能只改枚举
    - 售出态的关键词映射属平台知识，在 ``crawler/sources/<platform>/extract.json``，
      不在本模块
    - DTO 是线协议唯一真相源：前端镜像在 ``packages/contracts/src/watch.ts``，
      改字段先改这里再改那边。默认轮询间隔 ``DEFAULT_POLL_INTERVAL_SECONDS``
      也归这里——infrastructure 零依赖不能 import，domains/api 都从这里拿

使用示例：
    from contracts.watch import SoldState, WatchState, WatchListResponse
    if row.sold_state == SoldState.SOLD:
        ...
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class SoldState(StrEnum):
    """商品当前是否还能买到。"""

    UNKNOWN = "unknown"
    """状态文案未命中任何关键词，或还没轮询过。"""

    ON_SALE = "on_sale"
    """在售，可以买到。"""

    SOLD = "sold"
    """已售出——需求被验证的信号。"""

    DELISTED = "delisted"
    """卖家主动下架（未成交）。"""

    GONE = "gone"
    """详情已取不到（商品不存在），通常是售出或彻底删除。"""


class WatchState(StrEnum):
    """监控任务本身的开关。"""

    ACTIVE = "active"
    """正在按间隔轮询。"""

    PAUSED = "paused"
    """暂停轮询，保留价格历史。"""

    ARCHIVED = "archived"
    """已归档，不再轮询。"""


def is_finished(sold_state: str) -> bool:
    """商品是否已结束生命周期（售出 / 下架 / 消失），结束就不必再高频轮询。"""
    return sold_state in (SoldState.SOLD, SoldState.DELISTED, SoldState.GONE)


# ---------------------------------------------------------------------------
# 线协议：/v1/watch/* 请求与响应模型（唯一真相源，api 层直接复用）
# ---------------------------------------------------------------------------

DEFAULT_POLL_INTERVAL_SECONDS = 6 * 3600
"""默认轮询间隔：6 小时。词表与线协议共用这一个值。"""

MANUAL_POLL_MAX = 5
"""手动轮询一次最多触达的目标数（防止把同步接口拖成分钟级）。"""


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
