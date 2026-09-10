"""闲鱼 Crawler Source：搜索列表与商品详情。

职责：
    实现 BrowserCrawler 插头：搜索打开 goofish 搜索页做直播，列表优先 mtop，
    失败再 DOM 抽取；详情优先 Channel mtop，再页内 lib.mtop，再 detail_dom。
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
from src.channels.xianyu.risk import is_risk_control_text, page_is_punish
from src.channels.xianyu.risk_recovery import XianyuRiskRecovery
from src.channels.xianyu.session import Session
from src.crawler.core.base import BrowserCrawler, BrowserSessionOptions
from src.crawler.core.types import CrawlContext, CrawlItem, CrawlResult
from src.crawler.extraction.repair import repair_detail_dom, raise_repair_error
from src.crawler.sources.xianyu.repair_adapter import XianyuDetailRepairAdapter
from src.crawler.sources.xianyu.extractor import (
    DETAIL_DOM_JS,
    EXTRACT_JS,
    ITEM_URL,
    SCROLL_JS,
    SEARCH_URL,
    VIEW_JS,
    build_comment_request,
    build_list_request,
    comment_api_meta,
    comments_from_mtop,
    cookie_domain,
    detail_api_meta,
    detail_dom_arg,
    item_from_mtop_detail,
    item_from_view,
    items_from_mtop_search,
    items_from_payload,
    limits_meta,
    list_api_meta,
    list_api_name,
    search_dom_arg,
    session_expired_markers,
    view_arg,
)
from src.shared.errors import AppError, risk_control_error, session_expired_error

logger = logging.getLogger("dingda.crawler.xianyu")

COOKIE_DOMAIN = cookie_domain()
_LIMITS = limits_meta()
MAX_LIMIT = int(_LIMITS["max_limit"])
_DEFAULT_LIMIT = int(_LIMITS["default_limit"])
_SEARCH_API = list_api_name()
_LIST_META = list_api_meta()
_DETAIL_META = detail_api_meta()
_COMMENT_META = comment_api_meta()
_SEARCH_PAGE_SIZE = int(_LIST_META["page_size"])
_SEARCH_MAX_PAGES = int(_LIST_META["max_pages"])
_SESSION_EXPIRED = session_expired_markers()
_XIANYU_ADAPTER = XianyuDetailRepairAdapter()
_XIANYU_RISK = XianyuRiskRecovery()


class _RawPageView(Page):
    """把底层 Playwright page 适配成 BrowserPort Page，供 DOM 修复编排复用。

    仅修复编排实际用到的 ``url`` / ``evaluate`` / ``cookies`` 转发给底层页；
    其余插座方法为防御性 stub（修复流程不会调用）。
    """

    def __init__(self, raw: Any) -> None:
        self._raw = raw

    @property
    def url(self) -> str:
        return str(getattr(self._raw, "url", "") or "")

    async def evaluate(self, expression: str, arg: Any = None) -> Any:
        return await self._raw.evaluate(expression, arg)

    async def cookies(self) -> list[Cookie]:
        try:
            raw = await self._raw.context.cookies()
        except Exception:  # noqa: BLE001
            return []
        return list(raw or [])

    async def goto(self, url: str, **kwargs: Any) -> None:
        await self._raw.goto(url, **kwargs)

    async def content(self) -> str:
        return str(await self._raw.content())

    async def click(self, selector: str, *, timeout_ms: int = 10_000) -> None:
        raise AppError("crawler.page_unsupported", "修复页视图不支持 click")

    async def fill(self, selector: str, value: str, *, timeout_ms: int = 10_000) -> None:
        raise AppError("crawler.page_unsupported", "修复页视图不支持 fill")

    async def screenshot(self, path: Any = None, **kwargs: Any) -> bytes:
        raise AppError("crawler.page_unsupported", "修复页视图不支持 screenshot")

    async def add_cookies(self, cookies: Any, *, default_domain: str = "") -> None:
        raise AppError("crawler.page_unsupported", "修复页视图不支持 add_cookies")

    async def close(self) -> None:
        return None


class XianyuCrawler(BrowserCrawler):
    """闲鱼插头：复用基类浏览器会话；搜列表/详情优先 Channel mtop。"""

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
        """打开搜索页做直播；列表优先 mtop，失败再 DOM evaluate。"""
        from src.crawler.core.live import LIST_DWELL_S, dwell_for_viewer, emit_live_frame, live_frame_pump

        limit = _normalize_limit(ctx.meta.get("limit", _DEFAULT_LIMIT))
        cookie = str(ctx.meta.get("cookie") or "").strip()
        has_cookie = bool(cookie) or bool(self._options.cookies)
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

            items: list[CrawlItem] = []
            via = ""
            if cookie:
                await emit_live_frame(ctx, page, title=title, hint="mtop 拉取列表中…")
                try:
                    items = _search_via_mtop(Session.from_cookie_header(cookie), query, limit)
                    if items:
                        via = "mtop"
                except AppError as exc:
                    logger.info("search mtop failed, fallback dom: %s", exc.message)
                    await emit_live_frame(
                        ctx,
                        page,
                        title=title,
                        hint=f"mtop 失败，改 DOM · {exc.message[:40]}",
                    )
                except Exception:  # noqa: BLE001
                    logger.info("search mtop failed, fallback dom", exc_info=True)
                    await emit_live_frame(ctx, page, title=title, hint="mtop 失败，改 DOM 抽取")

            if not items:
                await emit_live_frame(ctx, page, title=title, hint="滚动加载列表")
                scroll_times = _scroll_times(limit)
                await raw_page.evaluate(SCROLL_JS, scroll_times)
                await emit_live_frame(ctx, page, title=title, hint="抽取商品")
                payload = await raw_page.evaluate(EXTRACT_JS, search_dom_arg(limit))
                if not isinstance(payload, dict):
                    raise AppError("crawler.extract_failed", "搜索页返回结构非预期")

                if not items_from_payload(payload) and payload.get("requiresAuth") and has_cookie:
                    logger.info("search requiresAuth with cookie, reload once")
                    await emit_live_frame(ctx, page, title=title, hint="登录态刷新中")
                    await raw_page.reload(wait_until="domcontentloaded")
                    await raw_page.wait_for_timeout(1500)
                    await raw_page.evaluate(SCROLL_JS, scroll_times)
                    payload = await raw_page.evaluate(EXTRACT_JS, search_dom_arg(limit))
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
                    payload = await raw_page.evaluate(EXTRACT_JS, search_dom_arg(limit))
                    if not isinstance(payload, dict):
                        raise AppError("crawler.extract_failed", "搜索页返回结构非预期")

                items = items_from_payload(payload)
                via = "dom"
                if not items and payload.get("requiresAuth"):
                    raise session_expired_error("xianyu")
                if not items and (payload.get("blocked") or _looks_risk(page)):
                    raise risk_control_error("搜索页触发验证码/安全验证（滑块未通过）")

            await emit_live_frame(
                ctx,
                page,
                title=title,
                hint=f"完成 · {len(items)} 条 · {via or '?'}",
            )
            await dwell_for_viewer(
                ctx,
                page,
                title=title,
                hint=f"浏览列表 · {len(items)} 条",
                seconds=LIST_DWELL_S,
            )
            logger.info("search done count=%s via=%s", len(items), via or "?")
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
                api=str(_DETAIL_META["api"]),
                data={str(_DETAIL_META["data_item_id_key"]): str(item_id)},
                version=str(_DETAIL_META["version"]),
                spm_cnt=str(_DETAIL_META["spm_cnt"]),
                auto_refresh=False,
            )
            item = item_from_mtop_detail(raw, str(item_id))
            if item.title:
                item = _with_comments(item, session)
                logger.info(
                    "detail done via=mtop item_id=%s title=%s comments=%s",
                    item.item_id,
                    item.title[:40],
                    len((item.raw or {}).get("comments") or []),
                )
                return CrawlResult(items=[item])
        except AppError as exc:
            if exc.code == "account.cookie_required":
                raise
            # 含 channel.risk：落到商品页；HTTP 已判明风控时开页后主动过滑块
            logger.info("detail mtop failed, fallback view: %s", exc.message)
            return await self._detail_via_page(
                ctx,
                str(item_id),
                force_slider=exc.code == "channel.risk" or "触发风控" in (exc.message or ""),
            )
        return await self._detail_via_page(ctx, str(item_id))

    async def _detail_via_page(
        self,
        ctx: CrawlContext,
        item_id: str,
        *,
        force_slider: bool = False,
    ) -> CrawlResult:
        """浏览器商品页：优先 lib.mtop，失败再 DOM（detail_dom）；风控则过滑块后重试。"""
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

            if force_slider or _looks_risk(page):
                await emit_live_frame(ctx, page, title=title, hint="检测到风控，正在过滑块…")
                await _pass_risk_or_raise(page, where="detail")
                await page.goto(ITEM_URL, params={"id": item_id})
                await raw_page.wait_for_timeout(2000)

            payload = await raw_page.evaluate(VIEW_JS, view_arg(item_id))
            if not isinstance(payload, dict):
                raise AppError("crawler.extract_failed", "商品详情页返回结构非预期")

            logger.info(
                "detail view payload error=%s code=%s msg=%s",
                payload.get("error"),
                payload.get("error_code"),
                str(payload.get("error_message") or "")[:120],
            )

            # 页内 mtop 常直接回 FAIL_SYS_USER_VALIDATE，URL 未必是 punish 页
            if (
                payload.get("error") == "blocked"
                or _looks_risk(page)
                or _payload_looks_risk(payload)
            ):
                await emit_live_frame(ctx, page, title=title, hint="详情触发风控，正在过滑块…")
                await _pass_risk_or_raise(page, where="detail")
                await page.goto(ITEM_URL, params={"id": item_id})
                await raw_page.wait_for_timeout(2000)
                payload = await raw_page.evaluate(VIEW_JS, view_arg(item_id))
                if not isinstance(payload, dict):
                    raise AppError("crawler.extract_failed", "商品详情页返回结构非预期")
                logger.info(
                    "detail view retry error=%s code=%s msg=%s",
                    payload.get("error"),
                    payload.get("error_code"),
                    str(payload.get("error_message") or "")[:120],
                )

            via = "view"
            err = payload.get("error")
            if err == "blocked" or _payload_looks_risk(payload):
                raise risk_control_error("商品详情页触发验证码/安全验证（滑块未通过）")
            err_blob = f"{payload.get('error_code') or ''} {payload.get('error_message') or ''}"
            if any(marker in err_blob for marker in _SESSION_EXPIRED):
                raise session_expired_error("xianyu")

            # mtop 未就绪 / 请求失败 → DOM 兜底（选择器见 extract.json detail_dom）
            if err or not str(payload.get("title") or "").strip():
                await emit_live_frame(ctx, page, title=title, hint="页内 mtop 失败，改 DOM 抽取…")
                logger.info(
                    "detail fallback dom item_id=%s view_error=%s",
                    item_id,
                    err or "empty-title",
                )
                payload = await raw_page.evaluate(DETAIL_DOM_JS, detail_dom_arg(item_id))
                if not isinstance(payload, dict):
                    raise AppError("crawler.extract_failed", "商品详情 DOM 返回结构非预期")
                via = "detail_dom"
                logger.info(
                    "detail dom payload error=%s title=%s",
                    payload.get("error"),
                    str(payload.get("title") or "")[:40],
                )
                if payload.get("error") == "blocked" or _looks_risk(page):
                    raise risk_control_error("商品详情 DOM 抽取时仍处于风控页")
                if payload.get("error") == "auth-required":
                    raise session_expired_error("xianyu")
                if payload.get("error"):
                    await emit_live_frame(ctx, page, title=title, hint="DOM 失效，尝试自动修复…")
                    result = await repair_detail_dom(
                        _RawPageView(raw_page),
                        _XIANYU_ADAPTER,
                        item_id=item_id,
                    )
                    if result.ok and result.payload is not None:
                        payload = result.payload
                        logger.info(
                            "detail dom repaired item_id=%s source=%s",
                            item_id,
                            result.patch.source if result.patch else "?",
                        )
                    else:
                        raise_repair_error(result)

            item = item_from_view(payload, item_id)
            if not item.title:
                raise AppError("crawler.not_found", f"未拿到商品 {item_id} 的标题", status_code=404)
            cookie = str(ctx.meta.get("cookie") or "").strip()
            if cookie:
                try:
                    item = _with_comments(item, Session.from_cookie_header(cookie))
                except Exception:  # noqa: BLE001
                    logger.info("detail view comments skipped item_id=%s", item_id, exc_info=True)
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
                "detail done via=%s item_id=%s title=%s comments=%s",
                via,
                item.item_id,
                item.title[:40],
                len((item.raw or {}).get("comments") or []),
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


def _payload_looks_risk(payload: dict[str, Any]) -> bool:
    """页内 mtop 返回是否含风控文案（URL 未必跳 punish）。"""
    blob = " ".join(
        str(payload.get(key) or "")
        for key in ("error", "error_code", "error_message")
    )
    return is_risk_control_text(blob)


async def _pass_risk_or_raise(page: Page, *, where: str) -> None:
    """委托 Channel 风控恢复：自动滑块 → 失败则有头窗口人工过。

    Channel 内部已按 ``auto_slider_enabled()`` 决定是否自动；失败再弹窗等人，
    超时/失败抛 ``channel.risk``。
    """
    logger.info("risk recovery start where=%s url=%s", where, page.url)
    await _XIANYU_RISK.recover_risk(page, where=where, url=page.url)


def _search_via_mtop(session: Session, query: str, limit: int) -> list[CrawlItem]:
    """分页调用列表 mtop（请求体见 extract.json）。"""
    from src.crawler.extraction.config import dig_first

    out: list[CrawlItem] = []
    page_number = 1
    rows_paths = list(_LIST_META.get("rows") or [])
    while len(out) < limit and page_number <= _SEARCH_MAX_PAGES:
        rows = min(_SEARCH_PAGE_SIZE, limit - len(out))
        logger.info(
            "search mtop page=%s rows=%s query=%s",
            page_number,
            rows,
            query,
        )
        raw = mtop_call(
            session,
            api=_SEARCH_API,
            data=build_list_request(page=page_number, query=query, rows=rows),
            version=str(_LIST_META["version"]),
            spm_cnt=str(_LIST_META["spm_cnt"]),
            auto_refresh=False,
        )
        batch = items_from_mtop_search(raw, limit=limit - len(out))
        if not batch:
            break
        out.extend(batch)
        result_list = dig_first(raw, rows_paths)
        if not isinstance(result_list, list) or len(result_list) < rows:
            break
        page_number += 1
    return out[:limit]


def _with_comments(item: CrawlItem, session: Session) -> CrawlItem:
    """详情成功后再拉一页留言，写入 raw.comments；失败则原样返回。"""
    try:
        raw = mtop_call(
            session,
            api=str(_COMMENT_META["api"]),
            data=build_comment_request(item_id=str(item.item_id)),
            version=str(_COMMENT_META["version"]),
            spm_cnt=str(_DETAIL_META["spm_cnt"]),
            auto_refresh=False,
        )
        comments = comments_from_mtop(raw)
        logger.info("comments done item_id=%s count=%s", item.item_id, len(comments))
        merged = {**(item.raw or {}), "comments": comments}
        return CrawlItem(
            item_id=item.item_id,
            title=item.title,
            url=item.url,
            price=item.price,
            raw=merged,
        )
    except Exception:  # noqa: BLE001
        logger.info("comments skipped item_id=%s", item.item_id, exc_info=True)
        return item


def _normalize_limit(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return _DEFAULT_LIMIT
    return min(MAX_LIMIT, max(1, n))


def _scroll_times(limit: int) -> int:
    """按目标条数多滚几屏，便于抽到接近 limit 的卡片。"""
    return max(3, min(14, (int(limit) + 7) // 8))
