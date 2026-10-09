"""单品详情直播端点。

职责：
    拉详情并 SSE 推送浏览器直播截图（frame）与最终结果（result）。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from api.routes.crawler._dto import CrawlerProductRequest, product_response
from api.routes.sse import sse_frame
from tools.account_cookie import resolve_crawl_cookie
from tools.product import ProductInput, run_product

logger = logging.getLogger("dingda.api.crawler")

router = APIRouter()


@router.post("/product/live")
async def product_detail_live(body: CrawlerProductRequest) -> StreamingResponse:
    """拉详情并 SSE 推送浏览器直播截图（frame）与最终结果（result）。"""
    platform = body.platform.strip().lower()
    item_id = body.item_id.strip()
    cookie = resolve_crawl_cookie(platform, body.cookie)
    logger.info(
        "crawler product live start platform=%s item_id=%s has_cookie=%s has_token=%s",
        platform,
        item_id,
        bool(cookie),
        bool(body.xsec_token),
    )

    queue: asyncio.Queue[tuple[str, dict[str, Any]] | None] = asyncio.Queue()

    async def on_live_frame(frame: dict[str, Any]) -> None:
        await queue.put(("frame", frame))

    async def runner() -> None:
        try:
            out = await run_product(
                ProductInput(
                    platform=platform,
                    item_id=item_id,
                    cookie=cookie,
                    xsec_token=body.xsec_token,
                ),
                on_live_frame=on_live_frame,
                live_frame_enabled=True,
            )
            resp = product_response(platform, item_id, out)
            if not out.ok:
                await queue.put(
                    (
                        "error",
                        {
                            "error_code": out.error_code,
                            "message": out.message or "商品详情失败",
                            "item_id": item_id,
                        },
                    )
                )
            else:
                await queue.put(("result", resp.model_dump()))
        except Exception as exc:  # noqa: BLE001
            logger.exception("crawler product live failed")
            await queue.put(
                (
                    "error",
                    {
                        "error_code": "tool.failed",
                        "message": str(exc),
                        "item_id": item_id,
                    },
                )
            )
        finally:
            await queue.put(None)

    task = asyncio.create_task(runner(), name="crawler-product-live")

    async def event_stream() -> AsyncIterator[str]:
        try:
            yield sse_frame(
                "status",
                {
                    "state": "running",
                    "label": "拉详情",
                    "hint": "正在打开笔记卡片…",
                    "item_id": item_id,
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
