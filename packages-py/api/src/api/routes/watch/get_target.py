"""监控详情端点。

职责：
    返回单条目标：当前快照 + 完整价格历史点 + 变更事件。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from api.routes.watch._dto import WatchDetailResponse, detail_response, empty_item
from domains.watch.service import get_detail

logger = logging.getLogger("dingda.api.watch")

router = APIRouter()


@router.get("/targets/{target_id}", response_model=WatchDetailResponse)
def get_watch_target(target_id: str) -> WatchDetailResponse:
    """单条监控：当前快照 + 完整价格历史点 + 变更事件。"""
    detail = get_detail(target_id)
    if detail is None:
        logger.info("watch detail not found target_id=%s", target_id)
        return WatchDetailResponse(
            ok=False,
            target=empty_item(target_id),
            points=[],
            changes=[],
        )
    return detail_response(detail)
