"""监控列表端点。

职责：
    返回监控目标列表，带涨跌额与售出态；可按状态过滤。
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from api.routes.watch._dto import WatchListResponse, to_item
from contracts.watch import WatchState
from domains.watch.service import list_views

router = APIRouter()


@router.get("/targets", response_model=WatchListResponse)
def list_watch_targets(
    state: WatchState | None = Query(default=None, description="按状态过滤；不传则全部"),
    limit: int = Query(default=200, ge=1, le=1000),
) -> WatchListResponse:
    """列出监控目标，带涨跌额与售出态。"""
    views = list_views(state=state.value if state else None, limit=limit)
    return WatchListResponse(total=len(views), targets=[to_item(view) for view in views])
