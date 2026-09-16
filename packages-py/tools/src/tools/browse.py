"""选品 Tool：browse（连贯浏览：列表 → 逐个点开详情）。

职责：
    契约（Input/Output）与执行放同一文件。
    一个浏览器会话内完成「打开搜索列表 → 点开第 1 个详情 → 返回 → 点开第 2 个…」，
    全程同一个 page，不来回开关页，直播是一段连续画面。

设计说明：
    - 与 search + 逐条 product 的区别：后者每次 detail 都重开页、且闲鱼 detail 默认
      走 mtop HTTP（根本不开页面，画面断掉）；browse 走 crawler.browse 的真页面路径
    - 只支持浏览器平台（当前 xianyu）；ali1688 无页面可逛
    - 不 import Playwright / Camoufox

使用示例：
    out = await run_browse(BrowseInput(platform="xianyu", query="露营椅", detail_count=3))
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from pydantic import BaseModel, Field

from browser.manager import get_browser_manager
from contracts.browser_port import LaunchOptions
from tools.account_cookie import resolve_crawl_cookie
from tools.headed import headless
from crawler.core.base import BrowserSessionOptions
from crawler.core.live import META_LIVE_CALLBACK, META_LIVE_ENABLED
from crawler.core.types import CrawlContext, CrawlItem
from crawler.registry import cookies_for, create_crawler, is_api_platform
from core.errors import AppError
from tools.product import ProductItem
from tools.recovery import with_crawl_recovery

logger = logging.getLogger("dingda.tools.browse")

TOOL_NAME = "browse"
TOOL_DESCRIPTION = (
    "连贯浏览：打开搜索列表，再一个一个点进商品详情，全程同一个浏览器页、连续直播。"
    "与 search 的区别：search 只给列表（详情另走接口、画面会断），browse 是真在页面上"
    "点开每个商品，用户能连续看到「列表 → 详情 → 返回 → 下一个」。"
    "适用：想实地看几款商品长什么样、核对详情与列表是否一致。"
    "当前支持闲鱼（xianyu）；ali1688 无页面可逛，请用 search。"
    "detail_count 控制点开几条（默认 3，上限 10，不超过 limit）。"
)
DEFAULT_TIMEOUT_S = 600.0


class BrowseInput(BaseModel):
    """连贯浏览入参。"""

    platform: str = Field(
        description="浏览平台：xianyu=闲鱼。ali1688 无页面可逛，不支持。"
    )
    query: str = Field(description="搜索关键词")
    limit: int = Field(
        default=10,
        ge=1,
        le=100,
        description="列表条数；默认 10。",
    )
    detail_count: int = Field(
        default=3,
        ge=1,
        le=10,
        description="要逐个点开详情的条数；默认 3，超过 limit 时按 limit 计。",
    )
    cookie: str | None = Field(
        default=None,
        description="可选登录 cookie；闲鱼建议已登录账号。",
    )
    proxy_url: str | None = Field(default=None, description="可选代理 URL；用户未要求则不要传。")


class BrowseOutput(BaseModel):
    """连贯浏览出参。"""

    ok: bool = True
    platform: str
    query: str
    items: list[ProductItem] = Field(
        default_factory=list,
        description="实际点开过的商品（按访问顺序）；一条都没点开时为列表条目",
    )
    error_code: str | None = None
    message: str | None = None


async def run_browse(
    inp: BrowseInput,
    *,
    on_live_frame: Any | None = None,
    live_frame_enabled: bool | None = None,
) -> BrowseOutput:
    """执行连贯浏览；一次 acquire 复用同一台浏览器。

    live_frame_enabled:
        - None：有 on_live_frame 则开，否则关
        - True / False：强制开/关（True 时仍需回调）
    """
    task_id = f"task-{uuid.uuid4().hex[:12]}"
    query = (inp.query or "").strip()
    platform = inp.platform.strip().lower()
    cookie = resolve_crawl_cookie(platform, inp.cookie)
    push_live = (
        bool(on_live_frame)
        if live_frame_enabled is None
        else bool(live_frame_enabled and on_live_frame)
    )
    logger.info(
        "tool start name=browse platform=%s query=%s limit=%s detail_count=%s task=%s live=%s",
        platform,
        query,
        inp.limit,
        inp.detail_count,
        task_id,
        push_live,
    )
    try:
        if is_api_platform(platform):
            raise AppError("browse.unsupported", f"{platform} 无页面可浏览", status_code=400)

        async def _run(run_cookie: str | None) -> list[CrawlItem]:
            return await _browse_browser(
                inp,
                task_id,
                query,
                platform=platform,
                cookie=run_cookie,
                on_live_frame=on_live_frame,
                live_frame_enabled=push_live,
            )

        items = await with_crawl_recovery(
            platform,
            _run,
            cookie=cookie,
            on_live_frame=on_live_frame,
        )
        rows = [_to_product_item(item) for item in items]
        logger.info("tool done name=browse visited=%s", len(rows))
        return BrowseOutput(ok=True, platform=platform, query=query, items=rows)
    except AppError as exc:
        logger.warning("tool failed name=browse code=%s", exc.code)
        return BrowseOutput(
            ok=False,
            platform=platform,
            query=query,
            error_code=exc.code,
            message=exc.message,
        )
    except Exception as exc:
        logger.exception("tool failed name=browse")
        return BrowseOutput(
            ok=False,
            platform=platform,
            query=query,
            error_code="tool.failed",
            message=str(exc),
        )


async def _browse_browser(
    inp: BrowseInput,
    task_id: str,
    query: str,
    *,
    platform: str,
    cookie: str | None = None,
    on_live_frame: Any | None = None,
    live_frame_enabled: bool = False,
) -> list[CrawlItem]:
    """浏览器 Source 连贯浏览：整段只 acquire/release 一次。"""
    manager = get_browser_manager()
    port = await manager.acquire(LaunchOptions(headless=headless()))
    try:
        options = BrowserSessionOptions(
            proxy_url=inp.proxy_url,
            cookies=cookies_for(platform, cookie),
        )
        crawler = create_crawler(platform, port, options)
        browse = getattr(crawler, "browse", None)
        if browse is None:
            raise AppError("browse.unsupported", f"{platform} 不支持连贯浏览", status_code=400)
        meta: dict[str, Any] = {
            "limit": inp.limit,
            "detail_count": inp.detail_count,
            "cookie": cookie or "",
            META_LIVE_ENABLED: bool(live_frame_enabled),
        }
        if on_live_frame is not None:
            meta[META_LIVE_CALLBACK] = on_live_frame
        result = await browse(CrawlContext(task_id=task_id, meta=meta), query)
        return list(result.items)
    finally:
        await manager.release(port)


def _to_product_item(item: CrawlItem) -> ProductItem:
    """CrawlItem → ProductItem（详情字段与 product 工具一致）。"""
    raw = item.raw if isinstance(item.raw, dict) else {}
    return ProductItem(
        item_id=item.item_id,
        title=item.title,
        url=item.url,
        price=item.price,
        seller_nick=_raw_str(raw, "seller_nick"),
        status=_raw_str(raw, "status"),
        sold_state=str(raw.get("sold_state") or "unknown"),
        want_count=_raw_str(raw, "want_count"),
        browse_count=_raw_str(raw, "browse_count"),
        image_url=_raw_str(raw, "image_url"),
        location=_raw_str(raw, "location"),
        desc=_raw_str(raw, "desc"),
        ocr_text=_raw_str(raw, "ocr_text"),
        content_text=_raw_str(raw, "content_text"),
    )


def _raw_str(raw: Any, key: str) -> str | None:
    """从 CrawlItem.raw 取非空字符串。"""
    if not isinstance(raw, dict):
        return None
    value = raw.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None
