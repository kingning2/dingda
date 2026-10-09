"""单品详情端点。

职责：
    拉取单品详情（闲鱼：价格、想要人数等；需登录 cookie）。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from api.routes.crawler._dto import (
    CrawlerProductRequest,
    CrawlerProductResponse,
    to_product_item,
)
from tools.product import ProductInput, run_product

logger = logging.getLogger("dingda.api.crawler")

router = APIRouter()


@router.post("/product", response_model=CrawlerProductResponse)
async def product_detail(body: CrawlerProductRequest) -> CrawlerProductResponse:
    """拉取单品详情（闲鱼：价格、想要人数等；需登录 cookie）。"""
    platform = body.platform.strip().lower()
    item_id = body.item_id.strip()
    logger.info("crawler product start platform=%s item_id=%s", platform, item_id)
    out = await run_product(
        ProductInput(
            platform=platform,
            item_id=item_id,
            cookie=body.cookie,
            xsec_token=body.xsec_token,
        )
    )
    if not out.ok or out.item is None:
        logger.info(
            "crawler product failed item_id=%s code=%s",
            item_id,
            out.error_code,
        )
        return CrawlerProductResponse(
            ok=False,
            platform=platform,
            error_code=out.error_code,
            message=out.message,
        )
    row = out.item
    logger.info(
        "crawler product done item_id=%s price=%s want=%s comments=%s",
        row.item_id,
        row.price,
        row.want_count,
        len(row.comments),
    )
    return CrawlerProductResponse(
        ok=True,
        platform=platform,
        item=to_product_item(platform, row),
    )
