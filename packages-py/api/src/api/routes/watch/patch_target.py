"""监控状态调整端点。

职责：
    调整监控状态（暂停/恢复/归档）或轮询间隔，返回调整后的完整详情。
"""

from __future__ import annotations

from fastapi import APIRouter

from api.routes.watch._dto import WatchPatchRequest, WatchDetailResponse, detail_response, empty_item
from domains.watch.service import get_detail, patch_target

router = APIRouter()


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
            target=empty_item(target_id),
            points=[],
            changes=[],
        )
    detail = get_detail(target_id)
    if detail is None:
        return WatchDetailResponse(
            ok=False,
            target=empty_item(target_id),
            points=[],
            changes=[],
        )
    return detail_response(detail)
