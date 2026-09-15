"""商品监控取数插头。

职责：
    用 ``tools.product`` 实现 ``domains.watch.base.ProductFetcher`` 插座，
    把 ProductOutput 映射成 ProductSnapshot 供后台轮询使用。

设计说明：
    - 插头放在 api：只有这一层同时依赖 ``domains``（插座）与 ``tools``（实现）
    - 后台轮询**不能有任何交互**，所以两处都要关：
      1. ``allow_login_recovery=False``：会话过期不弹扫码窗，让这次轮询失败，
         由 token 调度器去静默续期
      2. ``background_mode()``：撞风控只走自动滑块，不弹有头窗口阻塞 180s 等人
    - 失败不抛异常，用 ``ok=False`` + ``error_code`` 表达（插座契约）
"""

from __future__ import annotations

import logging

from channels.xianyu.risk_recovery import background_mode
from domains.watch.base import ProductSnapshot
from tools.product import ProductInput, run_product

logger = logging.getLogger("dingda.api.watch_feed")


async def fetch_product(
    *,
    platform: str,
    item_id: str,
    cookie: str | None,
) -> ProductSnapshot:
    """取一次商品详情；供 ``domains.watch.scheduler`` 轮询调用。"""
    logger.info("watch feed fetch platform=%s item_id=%s", platform, item_id)
    with background_mode():
        out = await run_product(
            ProductInput(platform=platform, item_id=item_id, cookie=cookie),
            allow_login_recovery=False,
        )
    if not out.ok or out.item is None:
        return ProductSnapshot(
            ok=False,
            error_code=out.error_code,
            error_message=out.message,
        )
    item = out.item
    return ProductSnapshot(
        ok=True,
        price_text=item.price,
        sold_state=item.sold_state,
        status_text=item.status,
        want_count=item.want_count,
        browse_count=item.browse_count,
        title=item.title,
    )
