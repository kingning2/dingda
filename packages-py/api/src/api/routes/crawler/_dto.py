"""Crawler 域 DTO 与映射。

职责：
    crawler 域的请求 / 响应 Pydantic 模型，以及
    SearchOutput / ProductOutput → HTTP 响应体的映射函数。

设计说明：
    - 响应模型是前端可直接渲染的商品 DTO，不透传 Tool 层模型
    - 搜索页 URL 由平台关键词拼出，供对话内嵌「页面」展示
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


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


class CrawlerProductComment(BaseModel):
    """闲鱼商品留言。"""

    author: str
    content: str
    time: str | None = None
    reply: str | None = None


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
    sold_state: str = Field(
        default="unknown",
        description="商品售出态：unknown / on_sale / sold / delisted / gone",
    )
    comments: list[CrawlerProductComment] = Field(default_factory=list)
    ocr_text: str | None = None
    content_text: str | None = None
    note_type: str | None = None
    xsec_token: str | None = None
    crawled_at: str


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


def search_url(platform: str, query: str) -> str:
    """拼平台搜索页 URL，供对话内嵌「页面」展示。"""
    q = query.strip()
    if platform == "xiaohongshu":
        return f"https://www.xiaohongshu.com/search_result?keyword={q}"
    if platform == "ali1688":
        return f"https://www.1688.com/selloffer/{q}.html"
    return f"https://www.goofish.com/search?q={q}"


def to_response(platform: str, query: str, out: Any) -> CrawlerSearchResponse:
    """SearchOutput → HTTP 响应体。"""
    now = datetime.now(timezone.utc).isoformat()
    url = search_url(platform, query)
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
            search_url=url,
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
        search_url=url,
    )


def to_product_item(platform: str, row: Any) -> CrawlerProductItem:
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
        sold_state=row.sold_state,
        comments=comments,
        ocr_text=row.ocr_text,
        content_text=row.content_text,
        crawled_at=now,
    )


def product_response(platform: str, item_id: str, out: Any) -> CrawlerProductResponse:
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
        item=to_product_item(platform, out.item),
    )
