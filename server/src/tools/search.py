"""选品 Tool：search（关键词 / 图 / 链接搜品）。

职责：
    契约（Input/Output）与执行放同一文件。
    浏览器平台：Crawler → BrowserPort；ali1688：ApiCrawler → Channel。

设计说明：
    - platform：xianyu / xiaohongshu / ali1688
    - ali1688 支持 query / image / url 三种入口
    - 不 import Playwright / Camoufox

使用示例：
    out = await run_search(SearchInput(platform="xianyu", query="露营椅", limit=20))
    out = await run_search(SearchInput(platform="ali1688", query="黑色卫衣"))
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from pydantic import BaseModel, Field, model_validator

from src.browser.manager import get_browser_manager
from src.browser.port import LaunchOptions
from src.crawler.account_cookie import resolve_crawl_cookie
from src.crawler.core.base import BrowserSessionOptions
from src.crawler.core.types import CrawlContext
from src.crawler.registry import cookies_for, create_api_crawler, create_crawler, is_api_platform
from src.shared.errors import AppError

logger = logging.getLogger("dingda.tools.search")

TOOL_NAME = "search"
TOOL_DESCRIPTION = (
    "在指定平台搜索商品/笔记列表，用于选品建样本池。"
    "闲鱼（xianyu）：验证关键词近期挂牌量与价位。"
    "小红书（xiaohongshu）：收趋势与可搜关键词。"
    "1688（ali1688）：官方找货；可用 query 文本搜，或 image 以图搜，或 url 链接找同款。"
    "返回 item_id / title / url / price。"
    "选品调研请多次调用、换词累积；单次 limit 建议 50～100（上限 100），总量争取 ≥100 条去重样本。"
)
DEFAULT_TIMEOUT_S = 60.0


class SearchInput(BaseModel):
    """搜品入参。"""

    platform: str = Field(
        description=(
            "爬取平台：xianyu=闲鱼；xiaohongshu=小红书；ali1688=1688 官方找货。"
        )
    )
    query: str = Field(
        default="",
        description=(
            "搜索关键词。xianyu/xiaohongshu 必填；"
            "ali1688 文本搜必填，以图/链接搜时可空或作附加词。"
        ),
    )
    image: str | None = Field(
        default=None,
        description="ali1688 以图搜：本地路径或图片 URL。与 url 二选一优先于纯文本。",
    )
    url: str | None = Field(
        default=None,
        description="ali1688 链接找同款：1688/淘宝/天猫商品链接或商品 ID。",
    )
    limit: int = Field(
        default=50,
        ge=1,
        le=100,
        description="返回条数，选品调研建议 50～100；单次上限 100。不够则换词再 search。",
    )
    sort: str | None = Field(
        default=None,
        description="ali1688 排序：price_asc / price_desc / sold_desc / yx_desc。",
    )
    score_level: str = Field(
        default="high",
        description="ali1688 相关性：high / medium / low。",
    )
    purchase_amount: int = Field(default=1, ge=1, description="ali1688 采购件数。")
    tags: str | None = Field(
        default="4306497",
        description="ali1688 TC 品池标签，逗号分隔；默认 4306497。",
    )
    ic_tags: str | None = Field(default=None, description="ali1688 IC 品池标签。")
    cookie: str | None = Field(
        default=None,
        description="可选登录 cookie；浏览器平台可用。ali1688 忽略。",
    )
    proxy_url: str | None = Field(default=None, description="可选代理 URL；浏览器平台可用。")
    cookie_domain: str | None = Field(
        default=None,
        description="cookie 注入域名；省略则用平台默认。",
    )

    @model_validator(mode="after")
    def _require_query_or_media(self) -> SearchInput:
        """浏览器平台必须有 query；ali1688 至少有 query/image/url 之一。"""
        platform = self.platform.strip().lower()
        if platform == "ali1688":
            if not (self.query or "").strip() and not self.image and not self.url:
                raise ValueError("ali1688 搜索需要 query、image 或 url 之一")
            return self
        if not (self.query or "").strip():
            raise ValueError("搜索需要 query")
        return self


class SearchItem(BaseModel):
    """单条搜品结果。"""

    item_id: str = Field(description="商品或笔记 id，后续拉详情用")
    title: str = Field(description="标题")
    url: str = Field(description="页面链接")
    price: str | None = Field(default=None, description="列表价，可能为空")
    seller_nick: str | None = Field(default=None, description="卖家/作者昵称，可能为空")
    xsec_token: str | None = Field(
        default=None,
        description="小红书搜索下发的 token，拉详情必须带回，否则会 300031",
    )
    image_url: str | None = Field(default=None, description="封面图，可能为空")


class SearchOutput(BaseModel):
    """搜品出参。"""

    ok: bool = True
    platform: str
    query: str
    items: list[SearchItem] = Field(default_factory=list)
    error_code: str | None = None
    message: str | None = None


async def run_search(
    inp: SearchInput,
    *,
    on_live_frame: Any | None = None,
    live_frame_enabled: bool | None = None,
) -> SearchOutput:
    """执行搜品：API 平台不启动浏览器。

    live_frame_enabled:
        - None：有 on_live_frame 则开，否则关
        - True / False：强制开/关（True 时仍需回调）
    """
    task_id = f"mcp-{uuid.uuid4().hex[:12]}"
    query = (inp.query or "").strip()
    cookie = resolve_crawl_cookie(inp.platform, inp.cookie)
    push_live = (
        bool(on_live_frame)
        if live_frame_enabled is None
        else bool(live_frame_enabled and on_live_frame)
    )
    logger.info(
        "tool start name=search platform=%s query=%s limit=%s task=%s has_cookie=%s live=%s",
        inp.platform,
        query,
        inp.limit,
        task_id,
        bool(cookie),
        push_live,
    )
    try:
        if is_api_platform(inp.platform):
            result_items = await _search_api(inp, task_id, query)
        else:
            result_items = await _search_browser(
                inp,
                task_id,
                query,
                cookie=cookie,
                on_live_frame=on_live_frame,
                live_frame_enabled=push_live,
            )

        rows = [
            SearchItem(
                item_id=item.item_id,
                title=item.title,
                url=item.url,
                price=item.price,
                seller_nick=_raw_str(item.raw, "seller_nick"),
                xsec_token=_raw_str(item.raw, "xsec_token"),
                image_url=_raw_str(item.raw, "image_url"),
            )
            for item in result_items
        ]
        logger.info("tool done name=search count=%s", len(rows))
        return SearchOutput(ok=True, platform=inp.platform, query=query, items=rows)
    except AppError as exc:
        logger.warning("tool failed name=search code=%s", exc.code)
        return SearchOutput(
            ok=False,
            platform=inp.platform,
            query=query,
            error_code=exc.code,
            message=exc.message,
        )
    except Exception as exc:
        logger.exception("tool failed name=search")
        return SearchOutput(
            ok=False,
            platform=inp.platform,
            query=query,
            error_code="tool.failed",
            message=str(exc),
        )

async def _search_api(inp: SearchInput, task_id: str, query: str) -> list[Any]:
    """API Source 搜品。"""
    meta = _ali1688_meta(inp)
    crawler = create_api_crawler(inp.platform)
    result = await crawler.search(CrawlContext(task_id=task_id, meta=meta), query)
    return result.items


async def _search_browser(
    inp: SearchInput,
    task_id: str,
    query: str,
    *,
    cookie: str | None = None,
    on_live_frame: Any | None = None,
    live_frame_enabled: bool = False,
) -> list[Any]:
    """浏览器 Source 搜品。"""
    from src.crawler.core.live import META_LIVE_CALLBACK, META_LIVE_ENABLED

    manager = get_browser_manager()
    port = await manager.acquire(LaunchOptions(headless=True))
    try:
        options = BrowserSessionOptions(
            proxy_url=inp.proxy_url,
            cookies=cookies_for(inp.platform, cookie),
            cookie_domain=inp.cookie_domain or "",
        )
        crawler = create_crawler(inp.platform, port, options)
        meta: dict[str, Any] = {
            "limit": inp.limit,
            META_LIVE_ENABLED: bool(live_frame_enabled),
        }
        if on_live_frame is not None:
            meta[META_LIVE_CALLBACK] = on_live_frame
        result = await crawler.search(
            CrawlContext(task_id=task_id, meta=meta),
            query,
        )
        return result.items
    finally:
        await manager.release(port)


def _ali1688_meta(inp: SearchInput) -> dict[str, Any]:
    """组装 ali1688 CrawlContext.meta。"""
    if inp.image:
        mode = "image"
    elif inp.url:
        mode = "link"
    else:
        mode = "text"

    meta: dict[str, Any] = {
        "mode": mode,
        "limit": inp.limit,
        "score_level": inp.score_level,
        "purchase_amount": inp.purchase_amount,
    }
    if inp.image:
        meta["image"] = inp.image
    if inp.url:
        meta["url"] = inp.url
    if inp.sort:
        meta["sort_type"] = inp.sort
    if inp.tags is not None:
        meta["tags"] = inp.tags
    if inp.ic_tags:
        meta["ic_tags"] = inp.ic_tags
    return meta


def _raw_str(raw: Any, key: str) -> str | None:
    """从 CrawlItem.raw 取非空字符串。"""
    if not isinstance(raw, dict):
        return None
    value = str(raw.get(key) or "").strip()
    return value or None
