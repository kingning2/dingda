"""商品监控 HTTP：加入监控、看列表/详情、调间隔、概览。

职责：
    把前端/脚本的监控请求接到 ``domains.watch``；本层只做入参校验与序列化，
    不算涨跌口径、不轮询、不发请求。

设计说明：
    - POST /v1/watch/targets              批量加入监控（同 platform+item_id 幂等）
    - GET  /v1/watch/targets              监控列表（带涨跌与售出态）
    - GET  /v1/watch/targets/{target_id}  单条：价格历史点 + 变更事件
    - PATCH/DELETE /v1/watch/targets/{id} 调状态/间隔、彻底移除
    - GET  /v1/watch/summary              概览：多少还在卖、多少卖掉了、多少降价了

使用示例：
    POST /v1/watch/targets {"items":[{"platform":"xianyu","item_id":"123"}],"poll_interval_seconds":21600}
    GET  /v1/watch/targets?state=active
"""

from __future__ import annotations

import logging
from dataclasses import asdict

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from contracts.watch import WatchState
from domains.watch.insight import WatchChange
from domains.watch.service import (
    WatchItemInput,
    WatchTargetDetail,
    WatchTargetView,
    add_targets,
    build_view,
    get_detail,
    list_views,
    patch_target,
    remove_target,
    summarize,
)
from infrastructure.db.watch import (
    DEFAULT_POLL_INTERVAL_SECONDS,
    WatchPointRow,
    WatchTargetRow,
)

logger = logging.getLogger("dingda.api.watch")

router = APIRouter(prefix="/v1/watch", tags=["watch"])


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


def _to_item(view: WatchTargetView) -> WatchTargetItem:
    """服务层视图 → HTTP DTO。"""
    return WatchTargetItem(**asdict(view))


def _to_point(row: WatchPointRow) -> WatchPointItem:
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


def _to_change(change: WatchChange) -> WatchChangeItem:
    """变更事件 → HTTP DTO。"""
    return WatchChangeItem(**asdict(change))


@router.post("/targets", response_model=WatchAddResponse)
def add_watch_targets(body: WatchAddRequest) -> WatchAddResponse:
    """批量加入监控；同 (platform, item_id) 已存在则复用原行，不重置价格历史。"""
    logger.info(
        "watch add start items=%s interval=%s",
        len(body.items),
        body.poll_interval_seconds,
    )
    rows = add_targets(
        [
            WatchItemInput(
                platform=item.platform,
                item_id=item.item_id,
                title=item.title,
                url=item.url,
                image_url=item.image_url,
                account_id=item.account_id,
            )
            for item in body.items
        ],
        poll_interval_seconds=body.poll_interval_seconds,
    )
    logger.info("watch add done added=%s", len(rows))
    return WatchAddResponse(added=len(rows), targets=[_to_item(row) for row in map(_view_of, rows)])


@router.get("/targets", response_model=WatchListResponse)
def list_watch_targets(
    state: WatchState | None = Query(default=None, description="按状态过滤；不传则全部"),
    limit: int = Query(default=200, ge=1, le=1000),
) -> WatchListResponse:
    """列出监控目标，带涨跌额与售出态。"""
    views = list_views(state=state.value if state else None, limit=limit)
    return WatchListResponse(total=len(views), targets=[_to_item(view) for view in views])


@router.get("/targets/{target_id}", response_model=WatchDetailResponse)
def get_watch_target(target_id: str) -> WatchDetailResponse:
    """单条监控：当前快照 + 完整价格历史点 + 变更事件。"""
    detail = get_detail(target_id)
    if detail is None:
        logger.info("watch detail not found target_id=%s", target_id)
        return WatchDetailResponse(
            ok=False,
            target=_empty_item(target_id),
            points=[],
            changes=[],
        )
    return _detail_response(detail)


@router.patch("/targets/{target_id}", response_model=WatchDetailResponse)
def patch_watch_target(target_id: str, body: WatchPatchRequest) -> WatchDetailResponse:
    """调整监控状态（暂停/恢复/归档）或轮询间隔。"""
    row = patch_target(
        target_id,
        state=body.state.value if body.state else None,
        poll_interval_seconds=body.poll_interval_seconds,
    )
    if row is None:
        return WatchDetailResponse(
            ok=False,
            target=_empty_item(target_id),
            points=[],
            changes=[],
        )
    detail = get_detail(target_id)
    if detail is None:
        return WatchDetailResponse(
            ok=False,
            target=_empty_item(target_id),
            points=[],
            changes=[],
        )
    return _detail_response(detail)


@router.delete("/targets/{target_id}", response_model=WatchDeleteResponse)
def delete_watch_target(target_id: str) -> WatchDeleteResponse:
    """彻底移除监控目标及其全部价格历史。想保留历史请改用 PATCH 归档。"""
    removed = remove_target(target_id)
    logger.info("watch delete target_id=%s removed=%s", target_id, removed)
    return WatchDeleteResponse(ok=removed, removed=removed)


@router.get("/summary", response_model=WatchSummaryResponse)
def watch_summary() -> WatchSummaryResponse:
    """概览：多少还在卖、多少卖掉了、多少降价了。"""
    return WatchSummaryResponse(**asdict(summarize()))


def _detail_response(detail: WatchTargetDetail) -> WatchDetailResponse:
    """服务层详情 → HTTP 响应。"""
    return WatchDetailResponse(
        target=_to_item(detail.target),
        points=[_to_point(row) for row in detail.points],
        changes=[_to_change(change) for change in detail.changes],
    )


def _view_of(row: WatchTargetRow) -> WatchTargetView:
    """库行 → 视图（复用服务层的涨跌口径）。"""
    return build_view(row)


def _empty_item(target_id: str) -> WatchTargetItem:
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
