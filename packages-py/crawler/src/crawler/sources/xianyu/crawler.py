"""闲鱼 Crawler Source：搜索列表与商品详情。

职责：
    实现 BrowserCrawler 插头：搜索打开 goofish 搜索页做直播，列表优先 mtop，
    失败再 DOM 抽取；详情优先 Channel mtop，再页内 lib.mtop，再 detail_dom；
    另有 browse 连贯浏览（一个 page 内 列表 → 逐个点开详情 → 返回列表）。
    命中 punish / 验证码时经 channels/xianyu/slider 自动过滑块后重试。

设计说明：
    - 平台：xianyu；禁止在本模块 import Playwright / Camoufox，仅经 BrowserPort
    - 过滑块与风控判定属 Channel（slider / risk），不进 Browser
    - 调用方：tools.search / tools.product / tools.browse、crawler/registry

使用示例：
    crawler = XianyuCrawler(browser_port, options)
    result = await crawler.search(ctx, "iPhone")
    result = await crawler.browse(ctx, "露营椅")
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from contracts.browser_port import (
    BrowserPort,
    Cookie,
    Page,
    PageEvent,
    PageEventInfo,
    PageEventHandler,
)
from channels.cookie_header import parse_cookie_header
from channels.xianyu.cookies import to_browser_cookies
from channels.xianyu.mtop import call as mtop_call
from channels.xianyu.risk import is_risk_control_text, page_is_punish
from channels.xianyu.slider import page_is_risk_block
from channels.xianyu.risk_recovery import XianyuRiskRecovery
from channels.xianyu.session import Session
from crawler.core.base import BrowserCrawler, BrowserSessionOptions
from crawler.core.types import CrawlContext, CrawlItem, CrawlResult
from crawler.extraction.repair import raise_repair_error
from crawler.extraction.repair.types import RepairResult
from crawler.sources.xianyu.repair_adapter import XianyuDetailRepairAdapter
from crawler.sources.xianyu.extractor import (
    DETAIL_DOM_JS,
    DETAIL_READY_JS,
    EXTRACT_JS,
    ITEM_URL,
    LIST_READY_JS,
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
    detail_ready_arg,
    item_from_mtop_detail,
    item_from_view,
    items_from_mtop_search,
    items_from_payload,
    limits_meta,
    list_api_meta,
    list_api_name,
    list_ready_arg,
    search_dom_arg,
    session_expired_markers,
    view_arg,
)
from core.errors import AppError, risk_control_error, session_expired_error

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
_DEFAULT_DETAIL_COUNT = 3
_MAX_DETAIL_COUNT = 10
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

    def on(self, event: PageEvent, handler: PageEventHandler) -> Callable[[], None]:
        raise AppError("crawler.page_unsupported", "修复页视图不支持事件订阅")

    async def wait_for_event(
        self,
        event: PageEvent,
        *,
        url_contains: str = "",
        timeout_ms: int = 15_000,
    ) -> PageEventInfo | None:
        raise AppError("crawler.page_unsupported", "修复页视图不支持 wait_for_event")

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

    async def wait_for_selector(
        self,
        selector: str,
        *,
        state: str = "visible",
        timeout_ms: int = 15_000,
    ) -> bool:
        raise AppError("crawler.page_unsupported", "修复页视图不支持 wait_for_selector")

    async def wait_for_load_state(
        self,
        state: str = "domcontentloaded",
        *,
        timeout_ms: int = 30_000,
    ) -> bool:
        raise AppError("crawler.page_unsupported", "修复页视图不支持 wait_for_load_state")

    async def wait_for_function(
        self,
        expression: str,
        arg: Any = None,
        *,
        timeout_ms: int = 15_000,
    ) -> bool:
        raise AppError("crawler.page_unsupported", "修复页视图不支持 wait_for_function")

    async def wait_for_response(
        self,
        url_contains: str,
        *,
        timeout_ms: int = 15_000,
    ) -> Any | None:
        raise AppError("crawler.page_unsupported", "修复页视图不支持 wait_for_response")

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
        from crawler.core.live import LIST_DWELL_S, dwell_for_viewer, emit_live_frame, live_frame_pump

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
            await _wait_list_ready(page)
            await emit_live_frame(ctx, page, title=title, hint="搜索页已就绪")
            pump = await live_frame_pump(ctx, page, title=title)

            if await _blocked(page, raw_page):
                await emit_live_frame(ctx, page, title=title, hint="检测到风控，正在过滑块…")
                await _pass_risk_or_raise(page, where="search")
                await page.goto(SEARCH_URL, params={"q": query})
                await _wait_list_ready(page)

            items, via = await self._collect_list(
                ctx,
                page,
                raw_page,
                query,
                limit,
                cookie=cookie,
                has_cookie=has_cookie,
                title=title,
            )

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

    async def _collect_list(
        self,
        ctx: CrawlContext,
        page: Page,
        raw_page: Any,
        query: str,
        limit: int,
        *,
        cookie: str,
        has_cookie: bool,
        title: str,
    ) -> tuple[list[CrawlItem], str]:
        """抽取搜索列表：优先 mtop，失败再 DOM；返回 ``(条目, 来源)``。

        设计说明：
            search 与 browse 共用这一段，避免两处抽取逻辑漂移。
        """
        from crawler.core.live import emit_live_frame

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
                await _wait_list_ready(page)
                await raw_page.evaluate(SCROLL_JS, scroll_times)
                payload = await raw_page.evaluate(EXTRACT_JS, search_dom_arg(limit))
                if not isinstance(payload, dict):
                    raise AppError("crawler.extract_failed", "搜索页返回结构非预期")

            if not items_from_payload(payload) and (payload.get("blocked") or await _blocked(page, raw_page)):
                await emit_live_frame(ctx, page, title=title, hint="搜索触发风控，正在过滑块…")
                await _pass_risk_or_raise(page, where="search")
                await page.goto(SEARCH_URL, params={"q": query})
                await _wait_list_ready(page)
                await raw_page.evaluate(SCROLL_JS, scroll_times)
                payload = await raw_page.evaluate(EXTRACT_JS, search_dom_arg(limit))
                if not isinstance(payload, dict):
                    raise AppError("crawler.extract_failed", "搜索页返回结构非预期")

            items = items_from_payload(payload)
            via = "dom"
            if not items and payload.get("requiresAuth"):
                raise session_expired_error("xianyu")
            if not items and (payload.get("blocked") or await _blocked(page, raw_page)):
                raise risk_control_error("搜索页触发验证码/安全验证（滑块未通过）")
        return items, via

    async def browse(self, ctx: CrawlContext, query: str) -> CrawlResult:
        """连贯浏览：一个 page 内 列表 → 逐个点开详情 → 返回列表 → 下一个。

        与「search 完再逐条 product」的区别：全程只开一个浏览器页，
        不来回开关页/浏览器，直播是一段连续的画面（能看到真实点进商品的过程）。

        meta：``limit`` / ``detail_count`` / ``cookie`` / 直播开关（同 search）。

        返回：实际点开过的商品（按访问顺序）；一条都没点开时退回列表条目。
        """
        from crawler.core.live import (
            DETAIL_DWELL_S,
            LIST_DWELL_S,
            dwell_for_viewer,
            emit_live_frame,
            live_frame_pump,
        )

        limit = _normalize_limit(ctx.meta.get("limit", _DEFAULT_LIMIT))
        detail_count = _normalize_detail_count(
            ctx.meta.get("detail_count", _DEFAULT_DETAIL_COUNT),
            limit,
        )
        cookie = str(ctx.meta.get("cookie") or "").strip()
        has_cookie = bool(cookie) or bool(self._options.cookies)
        logger.info(
            "browse start query=%s limit=%s detail_count=%s task=%s has_cookie=%s",
            query,
            limit,
            detail_count,
            ctx.task_id,
            has_cookie,
        )
        page = await self.open_page(ctx)
        pump = None
        try:
            title = f"闲鱼 · {query}"
            raw_page = _raw(page)

            await page.goto(SEARCH_URL, params={"q": query})
            await _wait_list_ready(page)
            await emit_live_frame(ctx, page, title=title, hint="搜索页已就绪")
            pump = await live_frame_pump(ctx, page, title=title)

            if await _blocked(page, raw_page):
                await emit_live_frame(ctx, page, title=title, hint="检测到风控，正在过滑块…")
                await _pass_risk_or_raise(page, where="search")
                await page.goto(SEARCH_URL, params={"q": query})
                await _wait_list_ready(page)

            items, via = await self._collect_list(
                ctx,
                page,
                raw_page,
                query,
                limit,
                cookie=cookie,
                has_cookie=has_cookie,
                title=title,
            )
            await emit_live_frame(
                ctx,
                page,
                title=title,
                hint=f"列表完成 · {len(items)} 条 · {via or '?'}",
            )
            await dwell_for_viewer(
                ctx,
                page,
                title=title,
                hint=f"浏览列表 · {len(items)} 条",
                seconds=LIST_DWELL_S,
            )

            targets = items[:detail_count]
            visited: list[CrawlItem] = []
            for index, item in enumerate(targets, start=1):
                item_id = str(item.item_id).strip()
                if not item_id:
                    continue
                await emit_live_frame(
                    ctx,
                    page,
                    title=title,
                    hint=f"打开第 {index}/{len(targets)} 个商品",
                )
                if not await _click_item_card(raw_page, item_id) or "item" not in (
                    page.url or ""
                ):
                    # 点不到卡片，或卡片开了新标签页（原页没动）→ 直接导航，
                    # 保证「列表 → 详情」始终发生在同一个可见页上
                    await page.goto(ITEM_URL, params={"id": item_id})
                await _wait_detail_ready(page)

                if await _blocked(page, raw_page):
                    await emit_live_frame(ctx, page, title=title, hint="详情触发风控，正在过滑块…")
                    await _pass_risk_or_raise(page, where="detail")
                    await page.goto(ITEM_URL, params={"id": item_id})
                    await _wait_detail_ready(page)

                payload = await raw_page.evaluate(VIEW_JS, view_arg(item_id))
                if not isinstance(payload, dict):
                    raise AppError("crawler.extract_failed", "商品详情页返回结构非预期")
                if payload.get("error") == "blocked" or _payload_looks_risk(payload):
                    await emit_live_frame(ctx, page, title=title, hint="详情触发风控，正在过滑块…")
                    await _pass_risk_or_raise(page, where="detail")
                    await page.goto(ITEM_URL, params={"id": item_id})
                    await _wait_detail_ready(page)
                    payload = await raw_page.evaluate(VIEW_JS, view_arg(item_id))
                    if not isinstance(payload, dict):
                        raise AppError("crawler.extract_failed", "商品详情页返回结构非预期")
                if payload.get("error") or not str(payload.get("title") or "").strip():
                    payload = await raw_page.evaluate(DETAIL_DOM_JS, detail_dom_arg(item_id))
                    if not isinstance(payload, dict):
                        raise AppError("crawler.extract_failed", "商品详情 DOM 返回结构非预期")
                    if payload.get("error") == "blocked" or await _blocked(page, raw_page):
                        raise risk_control_error("商品详情 DOM 抽取时仍处于风控页")

                detail = item_from_view(payload, item_id)
                if not detail.title:
                    detail = item
                await emit_live_frame(ctx, page, title=title, hint=f"详情 · {detail.title[:20]}")
                await dwell_for_viewer(
                    ctx,
                    page,
                    title=title,
                    hint=f"查看商品 · {detail.title[:16]}",
                    seconds=DETAIL_DWELL_S,
                )
                visited.append(detail)
                logger.info(
                    "browse detail ok %s/%s item_id=%s title=%s",
                    index,
                    len(targets),
                    item_id,
                    detail.title[:30],
                )

                try:
                    await raw_page.go_back(wait_until="domcontentloaded")
                except Exception:  # noqa: BLE001
                    logger.info("browse go_back failed item_id=%s", item_id, exc_info=True)
                await _wait_list_ready(page)
                if "search" not in (page.url or ""):
                    await page.goto(SEARCH_URL, params={"q": query})
                    await _wait_list_ready(page)
                await emit_live_frame(ctx, page, title=title, hint="返回列表 · 继续下一个")

            logger.info(
                "browse done query=%s list=%s visited=%s",
                query,
                len(items),
                len(visited),
            )
            return CrawlResult(items=visited or items)
        except AppError:
            raise
        except Exception:
            logger.exception("browse failed query=%s", query)
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
        from crawler.core.live import emit_live_frame, live_frame_pump

        page = await self.open_page(ctx)
        pump = None
        try:
            title = f"闲鱼详情 · {item_id}"
            raw_page = _raw(page)
            await page.goto(ITEM_URL, params={"id": item_id})
            await _wait_detail_ready(page)
            await emit_live_frame(ctx, page, title=title, hint="商品页已打开")
            pump = await live_frame_pump(ctx, page, title=title)

            if force_slider or await _blocked(page, raw_page):
                await emit_live_frame(ctx, page, title=title, hint="检测到风控，正在过滑块…")
                await _pass_risk_or_raise(page, where="detail")
                await page.goto(ITEM_URL, params={"id": item_id})
                await _wait_detail_ready(page)

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
                or await _blocked(page, raw_page)
                or _payload_looks_risk(payload)
            ):
                await emit_live_frame(ctx, page, title=title, hint="详情触发风控，正在过滑块…")
                await _pass_risk_or_raise(page, where="detail")
                await page.goto(ITEM_URL, params={"id": item_id})
                await _wait_detail_ready(page)
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
                if payload.get("error") == "blocked" or await _blocked(page, raw_page):
                    raise risk_control_error("商品详情 DOM 抽取时仍处于风控页")
                if payload.get("error") == "auth-required":
                    raise session_expired_error("xianyu")
                if payload.get("error"):
                    await emit_live_frame(ctx, page, title=title, hint="DOM 失效，尝试自动修复…")
                    page_url = str(getattr(page, "url", "") or "")
                    from crawler.extraction.repair.owner import RepairContext, get_repair_owner

                    decision = await get_repair_owner().on_dom_extract_failed(
                        RepairContext(
                            page=_RawPageView(raw_page),
                            adapter=_XIANYU_ADAPTER,
                            item_id=item_id,
                            url=page_url,
                            platform="xianyu",
                        )
                    )
                    if decision.action == "escalate":
                        assert decision.error is not None
                        raise decision.error
                    result = decision.result
                    if result is not None and result.ok and result.payload is not None:
                        payload = result.payload
                        logger.info(
                            "detail dom repaired item_id=%s source=%s",
                            item_id,
                            result.patch.source if result.patch else "?",
                        )
                    else:
                        raise_repair_error(result or RepairResult(ok=False, error="crawler.dom_repair_failed"))

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
            from crawler.core.live import DETAIL_DWELL_S, dwell_for_viewer

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


async def _wait_ready(
    page: Page,
    *,
    what: str,
    expression: str,
    arg: dict[str, Any],
) -> bool:
    """等页面就绪：先等浏览器层的加载状态，再等平台自己的内容判据。

    设计说明：
        加载状态（domcontentloaded）是平台无关的生命周期事件，先等它落定，
        免得还在导航中就跑去 evaluate；内容判据（卡片 / 风控 / 登录 / 空结果）
        才是「真的渲染出来了」的证明。
        两步都不抛：超时不算错误，调用方接着走 ``_blocked`` 与抽取分支，
        由它们决定成败——否则风控页会被误报成抽取失败。
    """
    timeout_ms = int(arg["timeout_ms"])
    await page.wait_for_load_state("domcontentloaded", timeout_ms=timeout_ms)
    ready = await page.wait_for_function(expression, arg, timeout_ms=timeout_ms)
    if not ready:
        logger.info("%s就绪判据未达成，按现状继续 url=%s", what, page.url)
    return ready


async def _wait_list_ready(page: Page) -> bool:
    """等搜索列表就绪（卡片出现 / 风控 / 需登录 / 空结果）。

    替代原先 goto 之后固定 ``wait_for_timeout(1200)``：固定时长在慢网络下
    必然随机失败，快网络下又白等。
    """
    return await _wait_ready(
        page,
        what="列表",
        expression=LIST_READY_JS,
        arg=list_ready_arg(),
    )


async def _wait_detail_ready(page: Page) -> bool:
    """等商品详情页就绪（信息块 + 价格/描述渲染完，或已命中风控/登录）。"""
    return await _wait_ready(
        page,
        what="详情",
        expression=DETAIL_READY_JS,
        arg=detail_ready_arg(),
    )


def _looks_risk(page: Page) -> bool:
    """当前 URL 是否已是 punish / captcha 页。"""
    return page_is_punish(getattr(page, "url", "") or "")


async def _blocked(page: Page, raw_page: Any) -> bool:
    """当前页是否卡在风控：URL punish，或页面 / 子 frame 里有验证弹窗。

    设计说明：
        只看 URL 会漏判——闲鱼常把滑块塞进 iframe，主文档 URL 不变，
        于是自动滑块压根没被触发，用户只能干看着一个弹窗没人管。
        ``page_is_risk_block`` 会扫主文档 + 各 frame 的 URL 与正文，并找滑块按钮。
    """
    if _looks_risk(page):
        return True
    try:
        return bool(await page_is_risk_block(raw_page))
    except Exception:  # noqa: BLE001
        logger.debug("risk block probe failed", exc_info=True)
        return False


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
    from crawler.extraction.config import dig_first

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


def _normalize_detail_count(value: Any, limit: int) -> int:
    """连贯浏览要点开几条详情：夹在 1 ~ min(limit, 上限) 之间。"""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return min(_DEFAULT_DETAIL_COUNT, max(1, limit))
    return min(_MAX_DETAIL_COUNT, max(1, limit), max(1, n))


async def _click_item_card(raw_page: Any, item_id: str) -> bool:
    """在搜索列表页真实点击该商品卡片；点不到返回 False（调用方改 goto）。

    设计说明：
        真人是从列表点进详情的，点得到就点，能少一次整页导航；
        卡片结构随 A/B 变化，点不到不算错误，交给 goto 兜底。
        用 locator.first 而不是 page.click：搜索页同 id 的锚点常不止一个，
        严格模式下 page.click 会直接报 multiple elements，白丢一次真点击。
    """
    selector = f'a[href*="id={item_id}"]'
    try:
        card = raw_page.locator(selector).first
        await card.scroll_into_view_if_needed(timeout=3000)
        await card.click(timeout=3000)
        return True
    except Exception:  # noqa: BLE001
        logger.info("browse card click fallback item_id=%s", item_id)
        return False
