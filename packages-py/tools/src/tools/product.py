"""选品 Tool：product（单品详情）。

职责：
    契约（Input/Output）与执行（Crawler → BrowserPort）放同一文件。
    供 registry / MCP 注册与调用；可选推送直播截图帧。

设计说明：
    - 闲鱼详情通常需要 cookie
    - 小红书详情需搜索下发的 xsec_token
    - 不 import Playwright / Camoufox

使用示例：
    out = await run_product(ProductInput(platform="xianyu", item_id="1", cookie="..."))
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from pydantic import BaseModel, Field

from browser.manager import get_browser_manager
from contracts.browser_port import LaunchOptions
from tools.account_cookie import resolve_crawl_cookie
from crawler.core.base import BrowserSessionOptions
from crawler.core.live import META_LIVE_CALLBACK, META_LIVE_ENABLED
from crawler.core.types import CrawlContext
from crawler.registry import cookies_for, create_crawler
from core.errors import AppError
from tools.recovery import with_crawl_recovery

logger = logging.getLogger("dingda.tools.product")

TOOL_NAME = "product"
TOOL_DESCRIPTION = (
    "按平台与 item_id 拉取单条详情。"
    "闲鱼 / 小红书图文：search 已会逐条拉详情；本工具用于对单条再核或补拉。"
    "item_id 必须来自 search 返回，不要手编。"
    "闲鱼详情需要已登录账号 cookie；缺失会失败（account.cookie_required），应先 login。"
    "禁止只凭 search 列表标题下结论；要用 desc / comments / want_count 等详情字段。"
    "小红书：会返回正文 desc、图片 OCR（ocr_text）以及合并文本 content_text；"
    "读笔记在说什么优先看 content_text。视频笔记暂不处理 OCR。"
    "小红书详情可传 xsec_token（若搜索结果里有）。"
    "不支持 ali1688（无独立详情 API）；1688 请用 search 或 compare。"
)
DEFAULT_TIMEOUT_S = 45.0


class ProductInput(BaseModel):
    """商品详情入参。"""

    platform: str = Field(
        description="与 search 相同：xianyu 或 xiaohongshu。不要填 ali1688。"
    )
    item_id: str = Field(description="来自 search 结果的商品/笔记 id")
    cookie: str | None = Field(
        default=None,
        description="账号 cookie。闲鱼详情强烈建议传入；缺失常会失败（account.cookie_required）。",
    )
    xsec_token: str | None = Field(
        default=None,
        description="小红书可选；打开笔记页时用。没有则省略。",
    )
    proxy_url: str | None = Field(default=None, description="可选代理 URL；用户未要求则不要传。")


class ProductComment(BaseModel):
    """闲鱼商品留言。"""

    author: str = Field(description="留言者昵称")
    content: str = Field(description="留言正文")
    time: str | None = Field(default=None, description="时间文案，可能为空")
    reply: str | None = Field(default=None, description="首条回复正文，可能为空")


class ProductItem(BaseModel):
    """单条商品详情。"""

    item_id: str = Field(description="商品或笔记 id")
    title: str = Field(description="标题")
    url: str = Field(description="页面链接")
    price: str | None = Field(default=None, description="价格，可能为空")
    seller_nick: str | None = Field(default=None, description="卖家昵称，可能为空")
    status: str | None = Field(default=None, description="状态文案，可能为空")
    want_count: str | None = Field(default=None, description="想要人数（闲鱼），可能为空")
    browse_count: str | None = Field(default=None, description="浏览量，可能为空")
    image_url: str | None = Field(default=None, description="封面图，可能为空")
    location: str | None = Field(default=None, description="地区，可能为空")
    desc: str | None = Field(default=None, description="正文描述（闲鱼 desc / 小红书笔记等），可能为空")
    comments: list[ProductComment] = Field(
        default_factory=list,
        description="闲鱼留言列表；无留言或未拉取时为空",
    )
    ocr_text: str | None = Field(
        default=None,
        description="图片 OCR 识别出的文字（小红书图文笔记），可能为空",
    )
    content_text: str | None = Field(
        default=None,
        description="正文 + 图片 OCR 合并文本（小红书），优先读这个了解笔记在说什么",
    )


class ProductOutput(BaseModel):
    """商品详情出参。"""

    ok: bool = True
    platform: str
    item_id: str
    item: ProductItem | None = None
    error_code: str | None = None
    message: str | None = None


async def run_product(
    inp: ProductInput,
    *,
    on_live_frame: Any | None = None,
    live_frame_enabled: bool | None = None,
) -> ProductOutput:
    """执行商品详情；可选推送直播截图帧。"""
    task_id = f"mcp-{uuid.uuid4().hex[:12]}"
    cookie = resolve_crawl_cookie(inp.platform, inp.cookie)
    push_live = (
        bool(on_live_frame)
        if live_frame_enabled is None
        else bool(live_frame_enabled and on_live_frame)
    )
    logger.info(
        "tool start name=product platform=%s item_id=%s task=%s has_cookie=%s live=%s",
        inp.platform,
        inp.item_id,
        task_id,
        bool(cookie),
        push_live,
    )

    async def _execute(run_cookie: str | None) -> ProductOutput:
        """一次抓取会话；登录失效由 with_crawl_recovery 扫码后整体重试。"""
        manager = get_browser_manager()
        port = None
        try:
            port = await manager.acquire(LaunchOptions(headless=True))
            options = BrowserSessionOptions(
                proxy_url=inp.proxy_url,
                cookies=cookies_for(inp.platform, run_cookie),
            )
            crawler = create_crawler(inp.platform, port, options)
            meta: dict[str, Any] = {
                "cookie": run_cookie or "",
                "xsec_token": inp.xsec_token or "",
                META_LIVE_ENABLED: bool(push_live),
            }
            if on_live_frame is not None:
                meta[META_LIVE_CALLBACK] = on_live_frame
            result = await crawler.detail(
                CrawlContext(task_id=task_id, meta=meta),
                inp.item_id,
            )
            if not result.items:
                return ProductOutput(
                    ok=False,
                    platform=inp.platform,
                    item_id=inp.item_id,
                    error_code="crawler.not_found",
                    message="未找到商品",
                )
            row = result.items[0]
            raw = row.raw if isinstance(row.raw, dict) else {}
            item = ProductItem(
                item_id=row.item_id,
                title=row.title,
                url=row.url,
                price=row.price,
                seller_nick=str(raw.get("seller_nick") or "") or None,
                status=str(raw.get("status") or "") or None,
                want_count=str(raw.get("want_count") or "") or None,
                browse_count=str(raw.get("browse_count") or "") or None,
                image_url=str(raw.get("image_url") or "") or None,
                location=str(raw.get("location") or "") or None,
                desc=str(raw.get("desc") or "") or None,
                comments=_comments_from_raw(raw.get("comments")),
                ocr_text=str(raw.get("ocr_text") or "") or None,
                content_text=str(raw.get("content_text") or "") or None,
            )
            logger.info("tool done name=product item_id=%s", item.item_id)
            return ProductOutput(
                ok=True,
                platform=inp.platform,
                item_id=inp.item_id,
                item=item,
            )
        finally:
            if port is not None:
                await manager.release(port)

    try:
        return await with_crawl_recovery(
            inp.platform,
            _execute,
            cookie=cookie,
            on_live_frame=on_live_frame,
        )
    except AppError as exc:
        logger.warning("tool failed name=product code=%s", exc.code)
        return ProductOutput(
            ok=False,
            platform=inp.platform,
            item_id=inp.item_id,
            error_code=exc.code,
            message=exc.message,
        )
    except Exception as exc:
        logger.exception("tool failed name=product")
        return ProductOutput(
            ok=False,
            platform=inp.platform,
            item_id=inp.item_id,
            error_code="tool.failed",
            message=str(exc),
        )


def _comments_from_raw(value: Any) -> list[ProductComment]:
    """raw.comments → ProductComment 列表。"""
    if not isinstance(value, list):
        return []
    out: list[ProductComment] = []
    for row in value:
        if not isinstance(row, dict):
            continue
        content = str(row.get("content") or "").strip()
        if not content:
            continue
        out.append(
            ProductComment(
                author=str(row.get("author") or "").strip() or "匿名",
                content=content,
                time=str(row.get("time") or "").strip() or None,
                reply=str(row.get("reply") or "").strip() or None,
            )
        )
    return out
