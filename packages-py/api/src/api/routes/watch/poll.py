"""手动轮询端点。

职责：
    立刻轮询几条监控目标（手动验证用）。

设计说明：
    - 后台定时轮询是常驻调度器的职责，本接口只用于「加完想马上看一眼」
    - 最多 ``MANUAL_POLL_MAX`` 条，逐条串行，间隔 3 秒
    - 注意耗时：走 mtop HTTP 时每条 1~3 秒；一旦回落浏览器商品页，单条可能要
      十几秒到数十秒（含自动过滑块），客户端超时要留够余量
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from api.lib.watch_feed import fetch_product
from api.routes.watch._dto import (
    MANUAL_POLL_MAX,
    WatchPollRequest,
    WatchPollResponse,
    WatchPollResult,
)
from domains.watch.scheduler import poll_targets_now

logger = logging.getLogger("dingda.api.watch")

router = APIRouter()


@router.post("/poll", response_model=WatchPollResponse)
async def poll_watch_targets(body: WatchPollRequest) -> WatchPollResponse:
    """立刻轮询几条（手动验证用）。

    后台定时轮询是常驻调度器的职责，本接口只用于「加完想马上看一眼」。
    最多 ``MANUAL_POLL_MAX`` 条，逐条串行，间隔 3 秒。

    注意耗时：走 mtop HTTP 时每条 1~3 秒；一旦回落浏览器商品页，单条可能要十几秒到
    数十秒（含自动过滑块）。所以本接口会同步阻塞，客户端超时要留够余量。
    """
    target_ids = body.target_ids
    if target_ids is not None and len(target_ids) > MANUAL_POLL_MAX:
        logger.info("watch manual poll trimmed %s -> %s", len(target_ids), MANUAL_POLL_MAX)
        target_ids = target_ids[:MANUAL_POLL_MAX]
    outcomes = await poll_targets_now(fetch_product, target_ids=target_ids)
    logger.info(
        "watch manual poll done polled=%s ok=%s",
        len(outcomes),
        sum(1 for item in outcomes if item.ok),
    )
    return WatchPollResponse(
        polled=len(outcomes),
        succeeded=sum(1 for item in outcomes if item.ok),
        results=[
            WatchPollResult(
                target_id=item.target_id,
                ok=item.ok,
                price=item.price,
                sold_state=item.sold_state,
                error=item.error,
            )
            for item in outcomes
        ],
    )
