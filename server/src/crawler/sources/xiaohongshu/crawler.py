"""小红书 Crawler Source：笔记搜索与详情。

职责：
    实现 BrowserCrawler 插头：打开 search_result / explore，evaluate __INITIAL_STATE__，
    标准化为 CrawlItem。

设计说明：
    - 平台：xiaohongshu；禁止 import Playwright / Camoufox，仅经 BrowserPort
    - 登录扫码仍在 channels/xiaohongshu；本模块只采集
    - 调用方：tools.search / tools.product、crawler/registry

使用示例：
    crawler = XiaohongshuCrawler(browser_port, options)
    result = await crawler.search(ctx, "咖啡")
"""

from __future__ import annotations

import logging
from typing import Any

from src.browser.port import BrowserPort, Cookie
from src.channels.cookie_header import parse_cookie_header
from src.channels.xiaohongshu.cookies import to_browser_cookies
from src.crawler.core.base import BrowserCrawler, BrowserSessionOptions
from src.crawler.core.types import CrawlContext, CrawlResult
from src.crawler.sources.xiaohongshu.extractor import (
    DETAIL_JS,
    DETAIL_READY_JS,
    NOTE_URL,
    SEARCH_JS,
    SEARCH_READY_JS,
    SEARCH_URL,
    item_from_detail,
    items_from_feeds,
)
from src.shared.errors import AppError, risk_control_error, session_expired_error

logger = logging.getLogger("dingda.crawler.xiaohongshu")

COOKIE_DOMAIN = ".xiaohongshu.com"
MAX_LIMIT = 50
_READY_TRIES = 50


class XiaohongshuCrawler(BrowserCrawler):
    """小红书插头：复用基类浏览器会话，页内抽 Vue 状态。"""

    platform = "xiaohongshu"

    def __init__(
        self,
        browser: BrowserPort,
        options: BrowserSessionOptions | None = None,
    ) -> None:
        opts = options or BrowserSessionOptions()
        if not opts.cookie_domain:
            opts = BrowserSessionOptions(
                proxy_url=opts.proxy_url,
                fingerprint_profile=opts.fingerprint_profile,
                cookies=opts.cookies,
                cookie_domain=COOKIE_DOMAIN,
            )
        super().__init__(browser, opts)

    @classmethod
    def cookies_from_header(cls, cookie: str | None) -> list[Cookie] | None:
        """小红书 cookie 注入 .xiaohongshu.com。"""
        if not cookie or not cookie.strip():
            return None
        return to_browser_cookies(parse_cookie_header(cookie))

    async def search(self, ctx: CrawlContext, query: str) -> CrawlResult:
        """按关键词抓取小红书搜索笔记。"""
        limit = _normalize_limit(ctx.meta.get("limit", 20))
        logger.info("search start query=%s limit=%s task=%s", query, limit, ctx.task_id)
        page = await self.open_page(ctx)
        try:
            await page.goto(
                SEARCH_URL,
                params={"keyword": query, "source": "web_explore_feed"},
            )
            raw_page = _raw(page)
            _raise_if_blocked(page.url)
            await _wait_ready(raw_page, SEARCH_READY_JS)
            payload = await raw_page.evaluate(SEARCH_JS)
            if not isinstance(payload, dict):
                raise AppError("crawler.extract_failed", "搜索页返回结构非预期")
            items = items_from_feeds(payload, limit=limit)
            logger.info("search done count=%s", len(items))
            return CrawlResult(items=items)
        except AppError:
            raise
        except Exception:
            logger.exception("search failed query=%s", query)
            raise
        finally:
            await self.close_page(page)

    async def detail(self, ctx: CrawlContext, item_id: str) -> CrawlResult:
        """打开笔记 explore 页，抽 noteDetailMap。"""
        note_id = str(item_id).strip()
        logger.info("detail start item_id=%s task=%s", note_id, ctx.task_id)
        page = await self.open_page(ctx)
        try:
            params = _detail_params(ctx)
            await page.goto(f"{NOTE_URL}/{note_id}", params=params)
            raw_page = _raw(page)
            _raise_if_blocked(page.url)
            await _wait_ready(raw_page, DETAIL_READY_JS)
            payload = await raw_page.evaluate(DETAIL_JS, note_id)
            if not isinstance(payload, dict) or not payload.get("note"):
                raise AppError("crawler.not_found", f"未拿到笔记 {note_id}", status_code=404)
            item = item_from_detail(payload, note_id)
            if not item.title:
                raise AppError("crawler.not_found", f"未拿到笔记 {note_id} 的标题", status_code=404)
            logger.info("detail done item_id=%s title=%s", item.item_id, item.title[:40])
            return CrawlResult(items=[item])
        except AppError:
            raise
        except Exception:
            logger.exception("detail failed item_id=%s", note_id)
            raise
        finally:
            await self.close_page(page)


def _raw(page: Any) -> Any:
    raw_page = getattr(page, "raw", None)
    if raw_page is None:
        raise AppError("crawler.page_unsupported", "当前 Page 无 raw，无法 evaluate")
    return raw_page


def _raise_if_blocked(url: str) -> None:
    blob = (url or "").lower()
    if "website-login/captcha" in blob:
        raise risk_control_error("小红书触发安全验证")
    if "xiaohongshu.com/login" in blob:
        raise session_expired_error("xiaohongshu")


async def _wait_ready(raw_page: Any, script: str) -> None:
    """轮询页内条件，直到数据就绪或次数用尽。"""
    last: Any = None
    for _ in range(_READY_TRIES):
        last = await raw_page.evaluate(script)
        if last:
            return
        wait = getattr(raw_page, "wait_for_timeout", None)
        if wait is not None:
            await wait(200)
    logger.warning("page data not ready last=%s", last)
    raise AppError("crawler.extract_failed", "页面数据未就绪")


def _detail_params(ctx: CrawlContext) -> dict[str, str] | None:
    token = str(ctx.meta.get("xsec_token") or "").strip()
    if not token:
        return None
    return {"xsec_token": token, "xsec_source": "pc_feed"}


def _normalize_limit(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 20
    return min(MAX_LIMIT, max(1, n))
