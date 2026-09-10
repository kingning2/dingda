"""Crawler HTTP：手动搜品 + 直播截图 SSE + 单品详情。

职责：
    把前端搜品/详情请求接到 tools.search / tools.product；
    /search/live、/product/live 用 SSE 推浏览器截图帧。不在此层写平台解析或 Playwright。

设计说明：
    - POST /v1/crawler/search → 一次性结果
    - POST /v1/crawler/search/live → SSE：frame / result / error / done
    - POST /v1/crawler/product → 单品详情
    - POST /v1/crawler/product/live → SSE：frame / result / error / done

使用示例：
    POST /v1/crawler/search/live {"platform":"xianyu","query":"露营椅","limit":8}
    POST /v1/crawler/product/live {"platform":"xiaohongshu","item_id":"...","xsec_token":"..."}
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.crawler.account_cookie import resolve_crawl_cookie
from src.tools.product import ProductInput, run_product
from src.tools.search import SearchInput, run_search

logger = logging.getLogger("dingda.api.crawler")

router = APIRouter(prefix="/v1/crawler", tags=["crawler"])


class CrawlerSearchRequest(BaseModel):
    """手动搜品请求。"""

    platform: str = Field(description="xianyu / ali1688 / xiaohongshu")
    query: str = Field(description="搜索关键词")
    limit: int = Field(default=12, ge=1, le=50, description="返回条数")
    cookie: str | None = Field(default=None, description="可选登录 cookie")


class CrawlerProductRequest(BaseModel):
    """单品详情请求。"""

    platform: str = Field(description="xianyu / xiaohongshu")
    item_id: str = Field(description="来自 search 的商品 id")
    cookie: str | None = Field(default=None, description="可选登录 cookie")
    xsec_token: str | None = Field(default=None, description="小红书可选")


class CrawlerProductItem(BaseModel):
    """前端可直接渲染的单条商品。"""

    id: str
    title: str
    price: str
    platform: str
    seller: str | None = None
    location: str | None = None
    image_url: str | None = None
    product_url: str | None = None
    want_count: str | None = None
    browse_count: str | None = None
    desc: str | None = None
    comments: list[CrawlerProductComment] = Field(default_factory=list)
    ocr_text: str | None = None
    content_text: str | None = None
    note_type: str | None = None
    xsec_token: str | None = None
    crawled_at: str


class CrawlerProductComment(BaseModel):
    """闲鱼商品留言。"""

    author: str
    content: str
    time: str | None = None
    reply: str | None = None


class CrawlerTaskStatus(BaseModel):
    """任务状态条。"""

    state: str
    label: str
    hint: str | None = None
    badge_class: str


class CrawlerSearchResponse(BaseModel):
    """搜品响应。"""

    task_id: str
    status: CrawlerTaskStatus
    items: list[CrawlerProductItem]
    total: int
    search_url: str | None = None
    error_code: str | None = None
    message: str | None = None


class CrawlerProductResponse(BaseModel):
    """单品详情响应。"""

    ok: bool = True
    platform: str
    item: CrawlerProductItem | None = None
    error_code: str | None = None
    message: str | None = None


def _search_url(platform: str, query: str) -> str:
    """拼平台搜索页 URL，供对话内嵌「页面」展示。"""
    q = query.strip()
    if platform == "xiaohongshu":
        return f"https://www.xiaohongshu.com/search_result?keyword={q}"
    if platform == "ali1688":
        return f"https://www.1688.com/selloffer/{q}.html"
    return f"https://www.goofish.com/search?q={q}"


def _to_response(platform: str, query: str, out: Any) -> CrawlerSearchResponse:
    """SearchOutput → HTTP 响应体。"""
    now = datetime.now(timezone.utc).isoformat()
    search_url = _search_url(platform, query)
    if not out.ok:
        return CrawlerSearchResponse(
            task_id=f"crawl-{platform}",
            status=CrawlerTaskStatus(
                state="error",
                label="失败",
                hint=out.message or out.error_code,
                badge_class="bg-destructive/15 text-destructive",
            ),
            items=[],
            total=0,
            search_url=search_url,
            error_code=out.error_code,
            message=out.message,
        )
    items = [
        CrawlerProductItem(
            id=item.item_id,
            title=item.title,
            price=item.price or "",
            platform=platform,
            seller=getattr(item, "seller_nick", None) or None,
            location=getattr(item, "location", None) or None,
            image_url=getattr(item, "image_url", None) or None,
            product_url=item.url or None,
            want_count=getattr(item, "want_count", None) or None,
            browse_count=getattr(item, "browse_count", None) or None,
            desc=getattr(item, "desc", None) or None,
            comments=[
                CrawlerProductComment(
                    author=c.author,
                    content=c.content,
                    time=c.time,
                    reply=c.reply,
                )
                for c in (getattr(item, "comments", None) or [])
            ],
            ocr_text=getattr(item, "ocr_text", None) or None,
            content_text=getattr(item, "content_text", None) or None,
            note_type=getattr(item, "note_type", None) or None,
            xsec_token=getattr(item, "xsec_token", None) or None,
            crawled_at=now,
        )
        for item in out.items
    ]
    return CrawlerSearchResponse(
        task_id=f"crawl-{platform}-{len(items)}",
        status=CrawlerTaskStatus(
            state="ready",
            label="完成",
            hint=f"共 {len(items)} 条",
            badge_class="bg-emerald-500/15 text-emerald-600",
        ),
        items=items,
        total=len(items),
        search_url=search_url,
    )


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


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
    resp = _to_response(platform, query, out)
    logger.info("crawler search done total=%s ok=%s", resp.total, out.ok)
    return resp


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
        item=_to_product_item(platform, row),
    )


def _to_product_item(platform: str, row: Any) -> CrawlerProductItem:
    """ProductItem → 前端商品 DTO（含描述与留言）。"""
    now = datetime.now(timezone.utc).isoformat()
    comments = [
        CrawlerProductComment(
            author=c.author,
            content=c.content,
            time=c.time,
            reply=c.reply,
        )
        for c in (row.comments or [])
    ]
    return CrawlerProductItem(
        id=row.item_id,
        title=row.title,
        price=row.price or "",
        platform=platform,
        seller=row.seller_nick,
        location=row.location,
        image_url=row.image_url,
        product_url=row.url or None,
        want_count=row.want_count,
        browse_count=row.browse_count,
        desc=row.desc,
        comments=comments,
        ocr_text=row.ocr_text,
        content_text=row.content_text,
        crawled_at=now,
    )


def _product_response(platform: str, item_id: str, out: Any) -> CrawlerProductResponse:
    """ProductOutput → HTTP 响应体。"""
    if not out.ok or out.item is None:
        return CrawlerProductResponse(
            ok=False,
            platform=platform,
            error_code=out.error_code,
            message=out.message,
        )
    return CrawlerProductResponse(
        ok=True,
        platform=platform,
        item=_to_product_item(platform, out.item),
    )


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
            resp = _product_response(platform, item_id, out)
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
            yield _sse(
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
                    yield _sse("done", {"ok": True})
                    break
                event, data = item
                yield _sse(event, data)
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
            resp = _to_response(platform, query, out)
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
                        "search_url": _search_url(platform, query),
                    },
                )
            )
        finally:
            await queue.put(None)

    task = asyncio.create_task(runner(), name="crawler-search-live")

    async def event_stream() -> AsyncIterator[str]:
        try:
            yield _sse(
                "status",
                {
                    "state": "running",
                    "label": "爬取中",
                    "hint": "正在打开浏览器…",
                    "search_url": _search_url(platform, query),
                    "has_cookie": bool(cookie),
                },
            )
            while True:
                item = await queue.get()
                if item is None:
                    yield _sse("done", {"ok": True})
                    break
                event, data = item
                yield _sse(event, data)
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
