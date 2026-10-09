"""搜品端点。

职责：
    执行一次平台搜品，返回列表与搜索页 URL（一次性，不直播）。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from api.routes.crawler._dto import CrawlerSearchRequest, CrawlerSearchResponse, to_response
from tools.account_cookie import resolve_crawl_cookie
from tools.search import SearchInput, run_search

logger = logging.getLogger("dingda.api.crawler")

router = APIRouter()


@router.post("/search", response_model=CrawlerSearchResponse)
async def search_products(body: CrawlerSearchRequest) -> CrawlerSearchResponse:
    """执行一次平台搜品，返回列表与搜索页 URL。"""
    platform = body.platform.strip().lower()
    query = body.query.strip()
    cookie = resolve_crawl_cookie(platform, body.cookie)
    logger.info(
        "crawler search start platform=%s query=%s limit=%s has_cookie=%s",
        platform,
        query,
        body.limit,
        bool(cookie),
    )
    out = await run_search(
        SearchInput(
            platform=platform,
            query=query,
            limit=body.limit,
            cookie=cookie,
        )
    )
    resp = to_response(platform, query, out)
    logger.info("crawler search done total=%s ok=%s", resp.total, out.ok)
    return resp
