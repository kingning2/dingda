"""监控删除端点。

职责：
    彻底移除监控目标及其全部价格历史；想保留历史请改用 PATCH 归档。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from api.routes.watch._dto import WatchDeleteResponse
from domains.watch.service import remove_target

logger = logging.getLogger("dingda.api.watch")

router = APIRouter()


@router.delete("/targets/{target_id}", response_model=WatchDeleteResponse)
def delete_watch_target(target_id: str) -> WatchDeleteResponse:
    """彻底移除监控目标及其全部价格历史。想保留历史请改用 PATCH 归档。"""
    removed = remove_target(target_id)
    logger.info("watch delete target_id=%s removed=%s", target_id, removed)
    return WatchDeleteResponse(ok=removed, removed=removed)
