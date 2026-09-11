"""选品 Tool：search（关键词 / 图 / 链接搜品）。

职责：
    契约（Input/Output）与执行放同一文件。
    浏览器平台：Crawler → BrowserPort；ali1688：ApiCrawler → Channel。
    闲鱼 search 在列表之后会逐条拉详情（描述 / 留言等），禁止只返回列表壳。

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
from src.crawler.core.types import CrawlContext, CrawlItem
from src.crawler.registry import cookies_for, create_api_crawler, create_crawler, is_api_platform
from src.shared.errors import AppError
from src.tools.product import ProductComment
from src.tools.recovery import with_crawl_recovery

logger = logging.getLogger("dingda.tools.search")

_AUTH_CODES = frozenset({"account.session_expired", "account.cookie_required"})


def _auth_error(exc: BaseException) -> bool:
    """登录类错误：交给外层 with_crawl_recovery 扫码后整体重试。"""
    return isinstance(exc, AppError) and exc.code in _AUTH_CODES

TOOL_NAME = "search"
TOOL_DESCRIPTION = (
    "在指定平台搜索商品/笔记，用于选品建样本池。"
    "闲鱼（xianyu）：打开搜索页做直播，列表优先 mtop（需 cookie），失败再 DOM；"
    "随后对返回的每一条逐条拉详情（desc / comments / want_count 等）；"
    "不能只看列表标题定价，结论必须基于详情字段。需要已登录 cookie，否则详情会跳过。"
    "小红书（xiaohongshu）：先搜列表，再对图文笔记逐条拉详情（正文 / 评论区 / OCR）；"
    "优先读 content_text；视频笔记暂时跳过详情，后面再处理。"
    "1688（ali1688）：官方找货；可用 query 文本搜，或 image 以图搜，或 url 链接找同款。"
    "返回 item_id / title / url / price；闲鱼/小红书图文另含详情字段。"
    "选品调研请多次调用、换词累积；单次 limit 建议 20～50（逐条详情较慢，上限 100），"
    "闲鱼去重样本争取 ≥100 条。"
)
DEFAULT_TIMEOUT_S = 300.0


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
        default=30,
        ge=1,
        le=100,
        description=(
            "返回条数。闲鱼会逐条拉详情，建议 20～50；上限 100。"
            "不够则换词再 search。"
        ),
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
        description="可选登录 cookie；闲鱼逐条详情强烈建议已登录账号。ali1688 忽略。",
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
    """单条搜品结果（闲鱼含逐条详情字段）。"""

    item_id: str = Field(description="商品或笔记 id，后续拉详情用")
    title: str = Field(description="标题")
    url: str = Field(description="页面链接")
    price: str | None = Field(default=None, description="列表价，可能为空")
    seller_nick: str | None = Field(default=None, description="卖家/作者昵称，可能为空")
    location: str | None = Field(default=None, description="地区，可能为空")
    want_count: str | None = Field(default=None, description="想要人数（闲鱼详情），可能为空")
    browse_count: str | None = Field(default=None, description="浏览量（闲鱼详情），可能为空")
    desc: str | None = Field(default=None, description="正文描述（闲鱼详情），可能为空")
    comments: list[ProductComment] = Field(
        default_factory=list,
        description="闲鱼留言；未拉详情或无留言时为空",
    )
    ocr_text: str | None = Field(
        default=None,
        description="小红书图片 OCR 文字，可能为空",
    )
    content_text: str | None = Field(
        default=None,
        description="小红书正文+OCR 合并文本；读笔记在说什么优先用这个",
    )
    note_type: str | None = Field(
        default=None,
        description="小红书笔记类型：normal / video；视频暂不拉详情",
    )
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
    """执行搜品；闲鱼在列表后逐条拉详情。

    live_frame_enabled:
        - None：有 on_live_frame 则开，否则关
        - True / False：强制开/关（True 时仍需回调）
    """
    task_id = f"mcp-{uuid.uuid4().hex[:12]}"
    query = (inp.query or "").strip()
    platform = inp.platform.strip().lower()
    cookie = resolve_crawl_cookie(platform, inp.cookie)
    push_live = (
        bool(on_live_frame)
        if live_frame_enabled is None
        else bool(live_frame_enabled and on_live_frame)
    )
    logger.info(
        "tool start name=search platform=%s query=%s limit=%s task=%s has_cookie=%s live=%s",
        platform,
        query,
        inp.limit,
        task_id,
        bool(cookie),
        push_live,
    )
    try:
        if is_api_platform(platform):
            result_items = await _search_api(inp, task_id, query)
        else:

            async def _run_browser(run_cookie: str | None) -> list[CrawlItem]:
                return await _search_browser(
                    inp,
                    task_id,
                    query,
                    platform=platform,
                    cookie=run_cookie,
                    on_live_frame=on_live_frame,
                    live_frame_enabled=push_live,
                )

            result_items = await with_crawl_recovery(
                platform,
                _run_browser,
                cookie=cookie,
                on_live_frame=on_live_frame,
            )

        rows = [_to_search_item(item) for item in result_items]
        logger.info(
            "tool done name=search count=%s detailed=%s",
            len(rows),
            sum(
                1
                for row in rows
                if row.desc or row.comments or row.want_count or row.ocr_text or row.content_text
            ),
        )
        return SearchOutput(ok=True, platform=platform, query=query, items=rows)
    except AppError as exc:
        logger.warning("tool failed name=search code=%s", exc.code)
        return SearchOutput(
            ok=False,
            platform=platform,
            query=query,
            error_code=exc.code,
            message=exc.message,
        )
    except Exception as exc:
        logger.exception("tool failed name=search")
        return SearchOutput(
            ok=False,
            platform=platform,
            query=query,
            error_code="tool.failed",
            message=str(exc),
        )


async def _search_api(inp: SearchInput, task_id: str, query: str) -> list[CrawlItem]:
    """API Source 搜品。"""
    meta = _ali1688_meta(inp)
    crawler = create_api_crawler(inp.platform)
    result = await crawler.search(CrawlContext(task_id=task_id, meta=meta), query)
    return list(result.items)


async def _search_browser(
    inp: SearchInput,
    task_id: str,
    query: str,
    *,
    platform: str,
    cookie: str | None = None,
    on_live_frame: Any | None = None,
    live_frame_enabled: bool = False,
) -> list[CrawlItem]:
    """浏览器 Source 搜品；闲鱼随后逐条 detail。"""
    from src.crawler.core.live import META_LIVE_CALLBACK, META_LIVE_ENABLED

    manager = get_browser_manager()
    port = await manager.acquire(LaunchOptions(headless=True))
    try:
        options = BrowserSessionOptions(
            proxy_url=inp.proxy_url,
            cookies=cookies_for(platform, cookie),
            cookie_domain=inp.cookie_domain or "",
        )
        crawler = create_crawler(platform, port, options)
        meta: dict[str, Any] = {
            "limit": inp.limit,
            "cookie": cookie or "",
            META_LIVE_ENABLED: bool(live_frame_enabled),
        }
        if on_live_frame is not None:
            meta[META_LIVE_CALLBACK] = on_live_frame
        result = await crawler.search(
            CrawlContext(task_id=task_id, meta=meta),
            query,
        )
        items = list(result.items)
        if platform == "xianyu":
            items = await _enrich_xianyu_details(
                crawler,
                items,
                task_id=task_id,
                cookie=cookie,
                live_meta=meta,
            )
        elif platform == "xiaohongshu":
            items = await _enrich_xiaohongshu_details(
                crawler,
                items,
                task_id=task_id,
                live_meta=meta,
            )
        return items
    finally:
        await manager.release(port)


async def _enrich_xianyu_details(
    crawler: Any,
    items: list[CrawlItem],
    *,
    task_id: str,
    cookie: str | None,
    live_meta: dict[str, Any],
) -> list[CrawlItem]:
    """对闲鱼列表逐条拉详情；失败则保留原列表项。"""
    from src.crawler.core.live import META_LIVE_ENABLED

    if not items:
        return items
    if not cookie:
        logger.warning(
            "search detail enrich skipped: no cookie count=%s",
            len(items),
        )
        return items

    total = len(items)
    logger.info("search detail enrich start platform=xianyu count=%s", total)
    # 逐条详情关掉直播 dwell，避免每条再停 3s+
    detail_meta = {**live_meta, META_LIVE_ENABLED: False}
    enriched: list[CrawlItem] = []
    for index, item in enumerate(items, start=1):
        item_id = str(item.item_id).strip()
        if not item_id:
            enriched.append(item)
            continue
        try:
            detail = await crawler.detail(
                CrawlContext(task_id=task_id, meta=detail_meta),
                item_id,
            )
            row = detail.items[0] if detail.items else None
            if row and row.title:
                enriched.append(row)
                logger.info(
                    "search detail enrich ok platform=xianyu %s/%s item_id=%s",
                    index,
                    total,
                    item_id,
                )
                continue
        except Exception as exc:  # noqa: BLE001
            if _auth_error(exc):
                raise
            logger.info(
                "search detail enrich failed platform=xianyu %s/%s item_id=%s",
                index,
                total,
                item_id,
                exc_info=True,
            )
        enriched.append(item)
    logger.info("search detail enrich done platform=xianyu count=%s", len(enriched))
    return enriched


async def _enrich_xiaohongshu_details(
    crawler: Any,
    items: list[CrawlItem],
    *,
    task_id: str,
    live_meta: dict[str, Any],
) -> list[CrawlItem]:
    """对小红书图文笔记逐条拉详情并 OCR；视频笔记暂跳过。"""
    from dataclasses import replace

    from src.crawler.core.live import META_LIVE_ENABLED
    from src.crawler.sources.xiaohongshu.extractor import is_video_note

    if not items:
        return items

    total = len(items)
    logger.info("search detail enrich start platform=xiaohongshu count=%s", total)
    enriched: list[CrawlItem] = []
    skipped_video = 0
    for index, item in enumerate(items, start=1):
        item_id = str(item.item_id).strip()
        raw = item.raw if isinstance(item.raw, dict) else {}
        if not item_id:
            enriched.append(item)
            continue
        if is_video_note(raw):
            skipped_video += 1
            enriched.append(
                replace(
                    item,
                    raw={
                        **raw,
                        "note_type": "video",
                        "skipped_reason": "video",
                        "skip_hint": "视频笔记暂跳过详情与 OCR",
                    },
                )
            )
            logger.info(
                "search detail enrich skip video %s/%s item_id=%s",
                index,
                total,
                item_id,
            )
            continue

        token = str(raw.get("xsec_token") or "").strip()
        detail_meta = {
            **live_meta,
            META_LIVE_ENABLED: False,
            "xsec_token": token,
        }
        try:
            detail = await crawler.detail(
                CrawlContext(task_id=task_id, meta=detail_meta),
                item_id,
            )
            row = detail.items[0] if detail.items else None
            if row and is_video_note(row.raw if isinstance(row.raw, dict) else None):
                skipped_video += 1
                row_raw = dict(row.raw or {})
                enriched.append(
                    replace(
                        row,
                        raw={
                            **row_raw,
                            "note_type": "video",
                            "skipped_reason": "video",
                            "skip_hint": "视频笔记暂跳过详情与 OCR",
                        },
                    )
                )
                logger.info(
                    "search detail enrich skip video-after-detail %s/%s item_id=%s",
                    index,
                    total,
                    item_id,
                )
                continue
            if row and row.title:
                enriched.append(row)
                ocr_chars = len(str((row.raw or {}).get("ocr_text") or ""))
                logger.info(
                    "search detail enrich ok platform=xiaohongshu %s/%s item_id=%s ocr_chars=%s",
                    index,
                    total,
                    item_id,
                    ocr_chars,
                )
                continue
        except Exception as exc:  # noqa: BLE001
            if _auth_error(exc):
                raise
            logger.info(
                "search detail enrich failed platform=xiaohongshu %s/%s item_id=%s",
                index,
                total,
                item_id,
                exc_info=True,
            )
        enriched.append(item)
    logger.info(
        "search detail enrich done platform=xiaohongshu count=%s skipped_video=%s",
        len(enriched),
        skipped_video,
    )
    return enriched


def _to_search_item(item: CrawlItem) -> SearchItem:
    """CrawlItem → SearchItem（含详情 / OCR 字段）。"""
    raw = item.raw if isinstance(item.raw, dict) else {}
    return SearchItem(
        item_id=item.item_id,
        title=item.title,
        url=item.url,
        price=item.price,
        seller_nick=_raw_str(raw, "seller_nick"),
        location=_raw_str(raw, "location"),
        want_count=_raw_str(raw, "want_count"),
        browse_count=_raw_str(raw, "browse_count"),
        desc=_raw_str(raw, "desc"),
        comments=_comments_from_raw(raw.get("comments")),
        ocr_text=_raw_str(raw, "ocr_text"),
        content_text=_raw_str(raw, "content_text"),
        note_type=_raw_str(raw, "note_type"),
        xsec_token=_raw_str(raw, "xsec_token"),
        image_url=_raw_str(raw, "image_url"),
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
    value = raw.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None
