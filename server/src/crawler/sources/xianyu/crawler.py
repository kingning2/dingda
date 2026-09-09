"""闲鱼 Crawler Source：搜索列表与商品详情。

职责：
    实现 BrowserCrawler 插头：搜索经 BrowserPort 打开 goofish 搜索页并 DOM 抽取；
    详情经 channels/xianyu/mtop 拉取并标准化为 CrawlItem。
    命中 punish / 验证码时经 channels/xianyu/slider 自动过滑块后重试。

设计说明：
    - 平台：xianyu；禁止在本模块 import Playwright / Camoufox，仅经 BrowserPort
    - 过滑块与风控判定属 Channel（slider / risk），不进 Browser
    - 调用方：tools.search / tools.product、crawler/registry

使用示例：
    crawler = XianyuCrawler(browser_port, options)
    result = await crawler.search(ctx, "iPhone")
"""

from __future__ import annotations

import logging
from typing import Any

from src.browser.port import BrowserPort, Cookie, Page
from src.channels.cookie_header import parse_cookie_header
from src.channels.xianyu.cookies import to_browser_cookies
from src.channels.xianyu.mtop import call as mtop_call
from src.channels.xianyu.risk import page_is_punish
from src.channels.xianyu.session import Session
from src.channels.xianyu.slider import auto_slider_enabled, clear_risk_cookies, try_solve_slider
from src.crawler.core.base import BrowserCrawler, BrowserSessionOptions
from src.crawler.core.types import CrawlContext, CrawlResult
from src.crawler.sources.xianyu.extractor import (
    EXTRACT_JS,
    ITEM_URL,
    SCROLL_JS,
    VIEW_JS,
    item_from_mtop_detail,
    item_from_view,
    items_from_payload,
)
from src.shared.errors import AppError, risk_control_error, session_expired_error

logger = logging.getLogger("dingda.crawler.xianyu")

SEARCH_URL = "https://www.goofish.com/search"
COOKIE_DOMAIN = ".goofish.com"
MAX_LIMIT = 100
_DETAIL_API = "mtop.taobao.idle.pc.detail"


class XianyuCrawler(BrowserCrawler):
    """闲鱼插头：复用基类浏览器会话；详情走 Channel mtop。"""

    platform = "xianyu"

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
        """闲鱼 cookie 按名映射淘系 / goofish 域名。"""
        if not cookie or not cookie.strip():
            return None
        return to_browser_cookies(parse_cookie_header(cookie))

    async def search(self, ctx: CrawlContext, query: str) -> CrawlResult:
        """按关键词抓取闲鱼搜索列表（DOM evaluate）；可选推送直播截图帧。"""
        from src.crawler.core.live import emit_live_frame, live_frame_pump

        limit = _normalize_limit(ctx.meta.get("limit", 20))
        has_cookie = bool(self._options.cookies)
        logger.info(
            "search start query=%s limit=%s task=%s has_cookie=%s",
            query,
            limit,
            ctx.task_id,
            has_cookie,
        )
        page = await self.open_page(ctx)
        pump = None
        try:
            title = f"闲鱼 · {query}"
            raw_page = _raw(page)

            await page.goto(SEARCH_URL, params={"q": query})
            await raw_page.wait_for_timeout(1200)
            await emit_live_frame(ctx, page, title=title, hint="搜索页已就绪")
            pump = await live_frame_pump(ctx, page, title=title)

            if _looks_risk(page):
                await emit_live_frame(ctx, page, title=title, hint="检测到风控，正在过滑块…")
                await _pass_risk_or_raise(page, where="search")
                await page.goto(SEARCH_URL, params={"q": query})
                await raw_page.wait_for_timeout(1200)

            await raw_page.wait_for_timeout(800)
            await emit_live_frame(ctx, page, title=title, hint="滚动加载列表")
            scroll_times = _scroll_times(limit)
            await raw_page.evaluate(SCROLL_JS, scroll_times)
            await emit_live_frame(ctx, page, title=title, hint="抽取商品")
            payload = await raw_page.evaluate(EXTRACT_JS, limit)
            if not isinstance(payload, dict):
                raise AppError("crawler.extract_failed", "搜索页返回结构非预期")

            if not items_from_payload(payload) and payload.get("requiresAuth") and has_cookie:
                logger.info("search requiresAuth with cookie, reload once")
                await emit_live_frame(ctx, page, title=title, hint="登录态刷新中")
                await raw_page.reload(wait_until="domcontentloaded")
                await raw_page.wait_for_timeout(1500)
                await raw_page.evaluate(SCROLL_JS, scroll_times)
                payload = await raw_page.evaluate(EXTRACT_JS, limit)
                if not isinstance(payload, dict):
                    raise AppError("crawler.extract_failed", "搜索页返回结构非预期")

            if not items_from_payload(payload) and (
                payload.get("blocked") or _looks_risk(page)
            ):
                await emit_live_frame(ctx, page, title=title, hint="搜索触发风控，正在过滑块…")
                await _pass_risk_or_raise(page, where="search")
                await page.goto(SEARCH_URL, params={"q": query})
                await raw_page.wait_for_timeout(1500)
                await raw_page.evaluate(SCROLL_JS, scroll_times)
                payload = await raw_page.evaluate(EXTRACT_JS, limit)
                if not isinstance(payload, dict):
                    raise AppError("crawler.extract_failed", "搜索页返回结构非预期")

            items = items_from_payload(payload)
            if not items and payload.get("requiresAuth"):
                raise session_expired_error("xianyu")
            if not items and (payload.get("blocked") or _looks_risk(page)):
                raise risk_control_error("搜索页触发验证码/安全验证（滑块未通过）")
            await emit_live_frame(ctx, page, title=title, hint=f"完成 · {len(items)} 条")
            from src.crawler.core.live import LIST_DWELL_S, dwell_for_viewer

            await dwell_for_viewer(
                ctx,
                page,
                title=title,
                hint=f"浏览列表 · {len(items)} 条",
                seconds=LIST_DWELL_S,
            )
            logger.info("search done count=%s", len(items))
            return CrawlResult(items=items)
        except AppError:
            raise
        except Exception:
            logger.exception("search failed query=%s", query)
            raise
        finally:
            if pump is not None:
                await pump.aclose()
            await self.close_page(page)

    async def detail(self, ctx: CrawlContext, item_id: str) -> CrawlResult:
        """优先 mtop HTTP；失败再走商品页内 lib.mtop。"""
        cookie = str(ctx.meta.get("cookie") or "").strip()
        if not cookie:
            raise AppError("account.cookie_required", "商品详情需要账号 cookie", status_code=401)
        logger.info("detail start item_id=%s task=%s", item_id, ctx.task_id)
        try:
            session = Session.from_cookie_header(cookie)
            raw = mtop_call(
                session,
                api=_DETAIL_API,
                data={"itemId": str(item_id)},
                version="1.0",
                spm_cnt="a21ybx.item.0.0",
                auto_refresh=False,
            )
            item = item_from_mtop_detail(raw, str(item_id))
            if item.title:
                logger.info(
                    "detail done via=mtop item_id=%s title=%s",
                    item.item_id,
                    item.title[:40],
                )
                return CrawlResult(items=[item])
        except AppError as exc:
            if exc.code == "account.cookie_required":
                raise
            # 含 channel.risk：落到商品页，由页内滑块恢复后再抽
            logger.info("detail mtop failed, fallback view: %s", exc.message)
        return await self._detail_via_page(ctx, str(item_id))

    async def _detail_via_page(self, ctx: CrawlContext, item_id: str) -> CrawlResult:
        """浏览器商品页内 mtop（对齐 goofish item view）；风控则过滑块后重试。"""
        from src.crawler.core.live import emit_live_frame, live_frame_pump

        page = await self.open_page(ctx)
        pump = None
        try:
            title = f"闲鱼详情 · {item_id}"
            raw_page = _raw(page)
            await page.goto(ITEM_URL, params={"id": item_id})
            await raw_page.wait_for_timeout(2000)
            await emit_live_frame(ctx, page, title=title, hint="商品页已打开")
            pump = await live_frame_pump(ctx, page, title=title)

            if _looks_risk(page):
                await emit_live_frame(ctx, page, title=title, hint="检测到风控，正在过滑块…")
                await _pass_risk_or_raise(page, where="detail")
                await page.goto(ITEM_URL, params={"id": item_id})
                await raw_page.wait_for_timeout(2000)

            payload = await raw_page.evaluate(VIEW_JS, item_id)
            if not isinstance(payload, dict):
                raise AppError("crawler.extract_failed", "商品详情页返回结构非预期")

            if payload.get("error") == "blocked" or _looks_risk(page):
                await emit_live_frame(ctx, page, title=title, hint="详情触发风控，正在过滑块…")
                await _pass_risk_or_raise(page, where="detail")
                await page.goto(ITEM_URL, params={"id": item_id})
                await raw_page.wait_for_timeout(2000)
                payload = await raw_page.evaluate(VIEW_JS, item_id)
                if not isinstance(payload, dict):
                    raise AppError("crawler.extract_failed", "商品详情页返回结构非预期")

            err = payload.get("error")
            if err == "blocked":
                raise risk_control_error("商品详情页触发验证码/安全验证（滑块未通过）")
            err_blob = f"{payload.get('error_code') or ''} {payload.get('error_message') or ''}"
            if "SESSION_EXPIRED" in err_blob:
                raise session_expired_error("xianyu")
            if err:
                raise AppError(
                    "channel.mtop_failed",
                    f"页内 mtop 失败 [{payload.get('error_code') or err}]: {payload.get('error_message') or ''}",
                    status_code=502,
                )
            item = item_from_view(payload, item_id)
            if not item.title:
                raise AppError("crawler.not_found", f"未拿到商品 {item_id} 的标题", status_code=404)
            await emit_live_frame(ctx, page, title=title, hint=f"完成 · {item.title[:20]}")
            from src.crawler.core.live import DETAIL_DWELL_S, dwell_for_viewer

            await dwell_for_viewer(
                ctx,
                page,
                title=title,
                hint=f"查看商品 · {item.title[:16]}",
                seconds=DETAIL_DWELL_S,
            )
            logger.info(
                "detail done via=view item_id=%s title=%s",
                item.item_id,
                item.title[:40],
            )
            return CrawlResult(items=[item])
        except AppError:
            raise
        except Exception:
            logger.exception("detail view failed item_id=%s", item_id)
            raise
        finally:
            if pump is not None:
                await pump.aclose()
            await self.close_page(page)


def _raw(page: Page) -> Any:
    """取出可 evaluate 的底层 page。"""
    raw_page = getattr(page, "raw", None)
    if raw_page is None:
        raise AppError("crawler.page_unsupported", "当前 Page 无 raw，无法 evaluate")
    return raw_page


def _looks_risk(page: Page) -> bool:
    """当前 URL 是否已是 punish / captcha 页。"""
    return page_is_punish(getattr(page, "url", "") or "")


async def _pass_risk_or_raise(page: Page, *, where: str) -> None:
    """在当前抓取页上自动过滑块；失败抛 channel.risk。"""
    if not auto_slider_enabled():
        raise risk_control_error(f"{where} 触发风控，但自动滑块已关闭（DINGDA_SLIDER_AUTO=0）")
    raw_page = _raw(page)
    context = getattr(page, "context", None)
    if context is None:
        raise AppError("crawler.page_unsupported", "当前 Page 无 context，无法过滑块")
    logger.info("risk recovery start where=%s url=%s", where, page.url)
    await clear_risk_cookies(context)
    ok, detail = await try_solve_slider(
        raw_page,
        context,
        max_retries=3,
        prefer_page_mouse=True,
    )
    logger.info("risk recovery done where=%s ok=%s detail=%s", where, ok, detail)
    if not ok:
        raise risk_control_error(f"{where} 风控滑块未通过：{detail}")


def _normalize_limit(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 20
    return min(MAX_LIMIT, max(1, n))


def _scroll_times(limit: int) -> int:
    """按目标条数多滚几屏，便于抽到接近 limit 的卡片。"""
    return max(3, min(14, (int(limit) + 7) // 8))
