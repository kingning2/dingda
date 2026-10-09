"""搜品直播端点。

职责：
    搜品并 SSE 推送浏览器直播截图（frame）与最终结果（result）。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from api.routes.crawler._dto import CrawlerSearchRequest, search_url, to_response
from api.routes.sse import sse_frame
from tools.account_cookie import resolve_crawl_cookie
from tools.search import SearchInput, run_search

logger = logging.getLogger("dingda.api.crawler")

router = APIRouter()


@router.post("/search/live")
async def search_products_live(body: CrawlerSearchRequest) -> StreamingResponse:
    """搜品并 SSE 推送浏览器直播截图（frame）与最终结果（result）。"""
    platform = body.platform.strip().lower()
    query = body.query.strip()
    cookie = resolve_crawl_cookie(platform, body.cookie)
    logger.info(
        "crawler search live start platform=%s query=%s limit=%s has_cookie=%s",
        platform,
        query,
        body.limit,
        bool(cookie),
    )

    queue: asyncio.Queue[tuple[str, dict[str, Any]] | None] = asyncio.Queue()

    async def on_live_frame(frame: dict[str, Any]) -> None:
        await queue.put(("frame", frame))

    async def runner() -> None:
        try:
            out = await run_search(
                SearchInput(
                    platform=platform,
                    query=query,
                    limit=body.limit,
                    cookie=cookie,
                ),
                on_live_frame=on_live_frame,
                live_frame_enabled=True,
            )
            resp = to_response(platform, query, out)
            if not out.ok:
                await queue.put(
                    (
                        "error",
                        {
                            "error_code": out.error_code,
                            "message": out.message or "爬虫搜品失败",
                            "search_url": resp.search_url,
                        },
                    )
                )
            else:
                await queue.put(("result", resp.model_dump()))
        except Exception as exc:  # noqa: BLE001
            logger.exception("crawler search live failed")
            await queue.put(
                (
                    "error",
                    {
                        "error_code": "tool.failed",
                        "message": str(exc),
                        "search_url": search_url(platform, query),
                    },
                )
            )
        finally:
            await queue.put(None)

    task = asyncio.create_task(runner(), name="crawler-search-live")

    async def event_stream() -> AsyncIterator[str]:
        try:
            yield sse_frame(
                "status",
                {
                    "state": "running",
                    "label": "爬取中",
                    "hint": "正在打开浏览器…",
                    "search_url": search_url(platform, query),
                    "has_cookie": bool(cookie),
                },
            )
            while True:
                item = await queue.get()
                if item is None:
                    yield sse_frame("done", {"ok": True})
                    break
                event, data = item
                yield sse_frame(event, data)
        finally:
            if not task.done():
                task.cancel()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
