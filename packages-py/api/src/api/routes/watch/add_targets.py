"""加入监控端点。

职责：
    批量把搜品结果加入监控；同 (platform, item_id) 已存在则复用原行，
    不重置价格历史。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from api.routes.watch._dto import WatchAddRequest, WatchAddResponse, to_item, view_of
from domains.watch.service import WatchItemInput, add_targets

logger = logging.getLogger("dingda.api.watch")

router = APIRouter()


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
    return WatchAddResponse(added=len(rows), targets=[to_item(row) for row in map(view_of, rows)])
