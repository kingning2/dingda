"""小红书 Crawler Source：笔记搜索与详情。

职责：
    实现 BrowserCrawler 插头：打开 search_result / explore，截获搜索 XHR
    或 DOM / __INITIAL_STATE__，标准化为 CrawlItem。

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

from src.browser.port import BrowserPort, Cookie, Page
from src.channels.cookie_header import parse_cookie_header
from src.channels.xiaohongshu.cookies import to_browser_cookies
from src.channels.xiaohongshu.risk_recovery import XiaohongshuRiskRecovery
from src.crawler.core.base import BrowserCrawler, BrowserSessionOptions
from src.crawler.core.recovery_hooks import run_step
from src.crawler.core.types import CrawlContext, CrawlResult
from src.crawler.extraction.repair import repair_detail_dom, raise_repair_error
from src.crawler.sources.xiaohongshu.repair_adapter import XiaohongshuDetailRepairAdapter
from src.crawler.sources.xiaohongshu.extractor import (
    DETAIL_HINT_JS,
    DETAIL_JS,
    DETAIL_READY_JS,
    DOM_COMMENTS_JS,
    DOM_DETAIL_JS,
    DOM_SEARCH_JS,
    NOTE_URL,
    PAGE_HINT_JS,
    SCROLL_COMMENTS_JS,
    SEARCH_JS,
    SEARCH_READY_JS,
    SEARCH_URL,
    behavior_meta,
    capture_http_methods,
    capture_url_hints,
    comment_api_matchers,
    comments_dom_arg,
    comments_from_captured,
    cookie_domain,
    detail_dom_arg,
    detail_goto_params,
    detail_hint_arg,
    feed_api_match_urls,
    item_from_detail,
    items_from_feeds,
    is_video_note,
    limits_meta,
    list_api_match_urls,
    note_error_codes,
    normalized_video_type,
    ocr_referer,
    page_hint_arg,
    search_dom_arg,
    search_goto_params,
    state_arg,
    url_block_rules,
)
from src.shared.errors import AppError, risk_control_error, session_expired_error

logger = logging.getLogger("dingda.crawler.xiaohongshu")

COOKIE_DOMAIN = cookie_domain()
_LIMITS = limits_meta()
_BEHAVIOR = behavior_meta()
MAX_LIMIT = int(_LIMITS["max_limit"])
_DEFAULT_LIMIT = int(_LIMITS["default_limit"])
_READY_TRIES = int(_BEHAVIOR["ready_tries"]) if isinstance(_BEHAVIOR.get("ready_tries"), int) else 50
_POLL_WAIT_MS = int(_BEHAVIOR["poll_wait_ms"]) if isinstance(_BEHAVIOR.get("poll_wait_ms"), int) else 250
_COMMENT_ROUNDS = int(_BEHAVIOR["comment_scroll_rounds"]) if isinstance(_BEHAVIOR.get("comment_scroll_rounds"), int) else 6
_COMMENT_WAIT_MS = int(_BEHAVIOR["comment_scroll_wait_ms"]) if isinstance(_BEHAVIOR.get("comment_scroll_wait_ms"), int) else 450
_ANON = str(_BEHAVIOR.get("anonymous_author") or "")
_SEARCH_API_MARKERS = list_api_match_urls()
_FEED_API_MARKERS = feed_api_match_urls()
_COMMENT_MATCHERS = comment_api_matchers()
_CAPTURE_HINTS = capture_url_hints()
_CAPTURE_METHODS = capture_http_methods()
_URL_BLOCKS = url_block_rules()
_NOTE_ERROR_CODES = note_error_codes()
_VIDEO_TYPE = normalized_video_type()
_XHS_ADAPTER = XiaohongshuDetailRepairAdapter()
_XHS_RISK = XiaohongshuRiskRecovery()


def _is_risk(exc: BaseException) -> bool:
    """步骤级风控判定：channel.risk / crawler.blocked 都算。"""
    return isinstance(exc, AppError) and exc.code in {"channel.risk", "crawler.blocked"}


def _needs_repair(item: Any) -> bool:
    """标题或作者缺失都算解析无果——作者空过会静默出坏数据。"""
    if item is None or not str(getattr(item, "title", "") or "").strip():
        return True
    raw = getattr(item, "raw", None)
    if not isinstance(raw, dict):
        return False
    return not str(raw.get("seller_nick") or "").strip()


class XiaohongshuCrawler(BrowserCrawler):
    """小红书插头：复用基类浏览器会话，优先截获搜索 XHR。"""

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
        """按关键词抓取小红书搜索笔记；可选推送直播截图帧。

        现网多数页面不再注入 ``__INITIAL_STATE__``。优先截获站点签名的
        ``search/notes`` 响应（事件里只存 Response，轮询时再读 body，避免
        async on 回调丢包）；再回退 DOM / 页内状态。
        """
        from src.crawler.core.live import emit_live_frame, live_frame_pump

        limit = _normalize_limit(ctx.meta.get("limit", _DEFAULT_LIMIT))
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
        pending: list[Any] = []
        seen_apis: list[str] = []
        captured: list[dict[str, Any]] = []

        def _on_response(response: Any) -> None:
            # 同步登记；body 延后 await，避免 async listener 未调度导致截获为空
            try:
                url = str(getattr(response, "url", "") or "")
                if any(hint in url for hint in _CAPTURE_HINTS):
                    status = getattr(response, "status", "?")
                    method = getattr(getattr(response, "request", None), "method", "?")
                    path = url.split("?", 1)[0]
                    mark = f"{status} {method} {path}"
                    if mark not in seen_apis and len(seen_apis) < 40:
                        seen_apis.append(mark)
                if not _is_search_notes_url(url):
                    return
                method = getattr(getattr(response, "request", None), "method", "")
                if method not in _CAPTURE_METHODS:
                    return
                pending.append(response)
                logger.info(
                    "命中 search/notes status=%s url=%s",
                    getattr(response, "status", "?"),
                    url.split("?", 1)[0],
                )
            except Exception:  # noqa: BLE001
                logger.debug("登记 search 响应失败", exc_info=True)

        try:
            title = f"小红书 · {query}"
            raw_page = _raw(page)
            raw_page.on("response", _on_response)

            async def _attempt() -> tuple[list[Any], str]:
                """一次搜索尝试；风控抛 channel.risk，由 run_step 恢复后重试。"""
                await emit_live_frame(ctx, page, title=title, hint="正在打开搜索页")
                await page.goto(
                    SEARCH_URL,
                    params=search_goto_params(query),
                )
                await emit_live_frame(ctx, page, title=title, hint="页面已打开")
                _raise_if_blocked(page.url)

                found: list[Any] = []
                how = ""
                for _ in range(_READY_TRIES):
                    await _drain_pending(pending, captured)
                    if captured:
                        found = _items_from_captured(captured, limit=limit)
                        if found:
                            how = "xhr"
                            break
                        if _captured_needs_login(captured):
                            raise session_expired_error("xiaohongshu")

                    ready = await raw_page.evaluate(SEARCH_READY_JS)
                    if ready:
                        state_payload = await raw_page.evaluate(SEARCH_JS, state_arg())
                        if isinstance(state_payload, dict):
                            found = items_from_feeds(state_payload, limit=limit)
                            if found:
                                how = "state"
                                break

                    dom_payload = await raw_page.evaluate(DOM_SEARCH_JS, search_dom_arg())
                    if isinstance(dom_payload, dict):
                        found = items_from_feeds(dom_payload, limit=limit)
                        if found:
                            how = "dom"
                            break

                    wait = getattr(raw_page, "wait_for_timeout", None)
                    if wait is not None:
                        await wait(_POLL_WAIT_MS)

                await _drain_pending(pending, captured)
                if not found and captured:
                    found = _items_from_captured(captured, limit=limit)
                    if found:
                        how = "xhr"
                    elif _captured_needs_login(captured):
                        raise session_expired_error("xiaohongshu")

                if not found and _looks_risk_page(page):
                    # 走到风控页：抛 channel.risk 交给 run_step 弹有头窗口等人过验证
                    raise risk_control_error("搜索触发了小红书安全验证")
                return found, how

            items, via = await run_step(
                "xiaohongshu.search",
                _attempt,
                page=page,
                risk=_XHS_RISK,
                is_risk=_is_risk,
            )
            pump = await live_frame_pump(ctx, page, title=title)

            if not items:
                hint = await raw_page.evaluate(PAGE_HINT_JS, page_hint_arg())
                logger.warning(
                    "search empty hint=%s apis=%s captured=%s",
                    hint,
                    seen_apis[:12],
                    len(captured),
                )
                if isinstance(hint, dict) and hint.get("login"):
                    raise session_expired_error("xiaohongshu")
                if not captured and not (isinstance(hint, dict) and hint.get("hasInitial")):
                    # 不再空等 INITIAL_STATE，避免误导性的 page data not ready
                    raise AppError(
                        "crawler.extract_failed",
                        "搜索页已打开但未拿到笔记数据（无 search/notes 与页内状态）",
                    )
                raise AppError("crawler.extract_failed", "页面数据未就绪")

            await emit_live_frame(ctx, page, title=title, hint=f"完成 · {len(items)} 条")
            from src.crawler.core.live import LIST_DWELL_S, dwell_for_viewer

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
            try:
                raw = getattr(page, "raw", None)
                if raw is not None:
                    raw.remove_listener("response", _on_response)
            except Exception:  # noqa: BLE001
                pass
            if pump is not None:
                await pump.aclose()
            await self.close_page(page)

    async def detail(self, ctx: CrawlContext, item_id: str) -> CrawlResult:
        """打开笔记弹层卡片（explore + xsec_token），抽标题/作者。

        现网详情不是独立 SSR 页，而是搜索结果上的弹层；裸开 explore 会
        ``error_code=300031``。必须带搜索下发的 ``xsec_token``，优先截获
        ``feed`` XHR，再回退弹层 DOM / 旧 INITIAL_STATE。
        """
        from src.crawler.core.live import emit_live_frame, live_frame_pump

        note_id = str(item_id).strip()
        token = str(ctx.meta.get("xsec_token") or "").strip()
        logger.info(
            "detail start item_id=%s task=%s has_token=%s",
            note_id,
            ctx.task_id,
            bool(token),
        )
        page = await self.open_page(ctx)
        pump = None
        pending: list[Any] = []
        captured: list[dict[str, Any]] = []
        comment_pending: list[Any] = []
        comment_bodies: list[dict[str, Any]] = []

        def _on_response(response: Any) -> None:
            try:
                url = str(getattr(response, "url", "") or "")
                method = getattr(getattr(response, "request", None), "method", "")
                if method not in _CAPTURE_METHODS:
                    return
                if _is_feed_url(url):
                    pending.append(response)
                    logger.info(
                        "命中 feed status=%s url=%s",
                        getattr(response, "status", "?"),
                        url.split("?", 1)[0],
                    )
                    return
                if _is_comment_url(url):
                    comment_pending.append(response)
                    logger.info(
                        "命中 comment/page status=%s url=%s",
                        getattr(response, "status", "?"),
                        url.split("?", 1)[0],
                    )
            except Exception:  # noqa: BLE001
                logger.debug("登记 feed/comment 响应失败", exc_info=True)

        try:
            title = f"小红书详情 · {note_id[:8]}"
            raw_page = _raw(page)
            raw_page.on("response", _on_response)
            params = _detail_params(ctx)
            if not params:
                logger.warning("detail 无 xsec_token，裸开极易 300031 item_id=%s", note_id)

            async def _attempt() -> tuple[Any, str]:
                """一次详情尝试；风控抛 channel.risk，由 run_step 恢复后重试。"""
                pending.clear()
                captured.clear()
                comment_pending.clear()
                comment_bodies.clear()
                # 先打开弹层给用户看，数据可从 feed HTTP / DOM 抽
                await page.goto(f"{NOTE_URL}/{note_id}", params=params)
                await emit_live_frame(ctx, page, title=title, hint="笔记卡片已打开")
                _raise_if_blocked(page.url)

                found = None
                how = ""
                for _ in range(_READY_TRIES):
                    await _drain_feed(pending, captured)
                    await _drain_comments(comment_pending, comment_bodies)
                    if captured:
                        found = _item_from_feed(captured, note_id)
                        if found and found.title:
                            how = "feed"
                            break

                    dom = await raw_page.evaluate(DOM_DETAIL_JS, detail_dom_arg(note_id))
                    if isinstance(dom, dict):
                        if dom.get("blocked"):
                            if _looks_risk_page(page):
                                raise risk_control_error("详情遇到小红书安全验证")
                            raise AppError(
                                "crawler.blocked",
                                "笔记暂时无法浏览（缺少 xsec_token 或风控）",
                            )
                        if dom.get("ready") and isinstance(dom.get("note"), dict):
                            found = item_from_detail(dom, note_id)
                            if found.title:
                                how = "dom"
                                break

                    ready = await raw_page.evaluate(DETAIL_READY_JS)
                    if ready:
                        payload = await raw_page.evaluate(DETAIL_JS, note_id)
                        if isinstance(payload, dict) and payload.get("note"):
                            found = item_from_detail(payload, note_id)
                            if found.title:
                                how = "state"
                                break

                    wait = getattr(raw_page, "wait_for_timeout", None)
                    if wait is not None:
                        await wait(_POLL_WAIT_MS)

                await _drain_feed(pending, captured)
                await _drain_comments(comment_pending, comment_bodies)
                if (not found or not found.title) and captured:
                    found = _item_from_feed(captured, note_id)
                    if found and found.title:
                        how = "feed"
                return found, how

            item, via = await run_step(
                "xiaohongshu.detail",
                _attempt,
                page=page,
                risk=_XHS_RISK,
                is_risk=_is_risk,
            )
            pump = await live_frame_pump(ctx, page, title=title)

            if _needs_repair(item):
                hint = await raw_page.evaluate(DETAIL_HINT_JS, detail_hint_arg())
                logger.warning("detail empty hint=%s captured=%s", hint, len(captured))
                if isinstance(hint, dict) and (
                    str(hint.get("error_code") or "") in _NOTE_ERROR_CODES
                    or any(code in str(hint.get("url") or "") for code in _NOTE_ERROR_CODES)
                ):
                    raise AppError(
                        "crawler.blocked",
                        "笔记暂时无法浏览，请用搜索结果里的 xsec_token 打开",
                    )
                # DOM 选择器可能失效：走指纹/AI 修复并写回 extract.json
                await emit_live_frame(ctx, page, title=title, hint="解析无果，尝试自动修复…")
                result = await repair_detail_dom(
                    _RawPageView(raw_page, page),
                    _XHS_ADAPTER,
                    item_id=note_id,
                )
                if result.ok and result.payload is not None:
                    repaired = item_from_detail(result.payload, note_id)
                    if repaired and repaired.title:
                        item = repaired
                        via = "detail_dom_repair"
                        logger.info(
                            "detail dom repaired item_id=%s source=%s",
                            note_id,
                            result.patch.source if result.patch else "?",
                        )
                # 标题拿不到才算硬失败；修好了就继续往下走
                if not item or not item.title:
                    raise_repair_error(result)
                if not str((item.raw or {}).get("seller_nick") or "").strip():
                    logger.warning(
                        "detail 作者字段仍为空 item_id=%s（选择器可能已失效）", note_id
                    )

            if is_video_note(item.raw if isinstance(item.raw, dict) else None):
                from dataclasses import replace

                raw = dict(item.raw or {})
                item = replace(
                    item,
                    raw={
                        **raw,
                        "note_type": _VIDEO_TYPE,
                        "skipped_reason": _VIDEO_TYPE,
                        "skip_hint": "视频笔记暂跳过详情与 OCR",
                    },
                )
                logger.info("detail skip video item_id=%s via=%s", item.item_id, via or "?")
                return CrawlResult(items=[item])

            item = await _with_comments(
                item,
                raw_page,
                comment_pending=comment_pending,
                comment_bodies=comment_bodies,
            )
            item = _enrich_with_ocr(item)
            if not str((item.raw or {}).get("ocr_text") or "").strip():
                item = await _enrich_with_page_ocr(item, page)
            await emit_live_frame(ctx, page, title=title, hint=f"完成 · {item.title[:20]}")
            from src.crawler.core.live import DETAIL_DWELL_S, dwell_for_viewer

            await dwell_for_viewer(
                ctx,
                page,
                title=title,
                hint=f"查看笔记 · {item.title[:16]}",
                seconds=DETAIL_DWELL_S,
            )
            logger.info(
                "detail done item_id=%s via=%s title=%s ocr_chars=%s comments=%s",
                item.item_id,
                via or "?",
                item.title[:40],
                len(str((item.raw or {}).get("ocr_text") or "")),
                len((item.raw or {}).get("comments") or []),
            )
            return CrawlResult(items=[item])
        except AppError:
            raise
        except Exception:
            logger.exception("detail failed item_id=%s", note_id)
            raise
        finally:
            try:
                raw = getattr(page, "raw", None)
                if raw is not None:
                    raw.remove_listener("response", _on_response)
            except Exception:  # noqa: BLE001
                pass
            if pump is not None:
                await pump.aclose()
            await self.close_page(page)


def _enrich_with_ocr(item: Any) -> Any:
    """小红书详情：对笔记图片做 OCR，写入 raw.ocr_text。"""
    from dataclasses import replace

    from src.crawler.core.types import CrawlItem
    from src.crawler.ocr import ocr_image_urls

    if not isinstance(item, CrawlItem):
        return item
    raw = dict(item.raw or {})
    urls = raw.get("image_urls")
    if not isinstance(urls, list) or not urls:
        cover = str(raw.get("image_url") or "").strip()
        urls = [cover] if cover else []
    str_urls = [str(u).strip() for u in urls if str(u).strip().startswith("http")]
    if not str_urls:
        return item
    logger.info("xhs ocr start images=%s item_id=%s", len(str_urls[:3]), item.item_id)
    ocr_text = ocr_image_urls(str_urls, referer=item.url or ocr_referer())
    if not ocr_text:
        return item
    return replace(item, raw=_merge_ocr_raw(raw, ocr_text))


async def _enrich_with_page_ocr(item: Any, page: Any) -> Any:
    """图片 URL OCR 失败时，对当前页截图再识字（兜底）。"""
    from dataclasses import replace

    from src.crawler.core.types import CrawlItem
    from src.crawler.ocr import ocr_image_bytes

    if not isinstance(item, CrawlItem):
        return item
    try:
        shot = await page.screenshot(image_type="jpeg", quality=70)
    except Exception:  # noqa: BLE001
        logger.debug("xhs page screenshot for ocr failed", exc_info=True)
        return item
    logger.info("xhs ocr fallback page screenshot item_id=%s", item.item_id)
    ocr_text = ocr_image_bytes(shot)
    if not ocr_text:
        return item
    raw = dict(item.raw or {})
    return replace(item, raw=_merge_ocr_raw(raw, ocr_text))


def _merge_ocr_raw(raw: dict[str, Any], ocr_text: str) -> dict[str, Any]:
    """把 OCR 文本写入 raw（ocr_text / content_text）。"""
    out = dict(raw)
    out["ocr_text"] = ocr_text
    desc = str(out.get("desc") or "").strip()
    if desc and ocr_text:
        out["content_text"] = f"{desc}\n\n【图片文字】\n{ocr_text}"
    elif ocr_text:
        out["content_text"] = ocr_text
    logger.info("xhs ocr done chars=%s", len(ocr_text))
    return out


def _raw(page: Any) -> Any:
    raw_page = getattr(page, "raw", None)
    if raw_page is None:
        raise AppError("crawler.page_unsupported", "当前 Page 无 raw，无法 evaluate")
    return raw_page


class _RawPageView(Page):
    """底层 Playwright page → BrowserPort Page，供 DOM 修复编排复用。

    仅修复编排用到的 ``url`` / ``evaluate`` / ``cookies`` 转发；其余为防御性 stub。
    """

    def __init__(self, raw: Any, source_page: Page | None = None) -> None:
        self._raw = raw
        self._source = source_page

    @property
    def url(self) -> str:
        if self._source is not None:
            return str(getattr(self._source, "url", "") or "")
        return str(getattr(self._raw, "url", "") or "")

    async def evaluate(self, expression: str, arg: Any = None) -> Any:
        return await self._raw.evaluate(expression, arg)

    async def cookies(self) -> list[Cookie]:
        if self._source is not None:
            try:
                return list(await self._source.cookies())
            except Exception:  # noqa: BLE001
                pass
        try:
            return list(await self._raw.context.cookies() or [])
        except Exception:  # noqa: BLE001
            return []

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


def _looks_risk_page(page: Any) -> bool:
    """当前页 URL 是否命中 blocked_url（安全验证）。"""
    blob = (getattr(page, "url", "") or "").lower()
    return any(
        marker.lower() in blob
        for marker in _URL_BLOCKS.get("blocked_url") or []
    )


def _raise_if_blocked(url: str) -> None:
    blob = (url or "").lower()
    if any(marker.lower() in blob for marker in _URL_BLOCKS.get("blocked_url") or []):
        raise risk_control_error("小红书触发安全验证")
    if any(marker.lower() in blob for marker in _URL_BLOCKS.get("login_url") or []):
        raise session_expired_error("xiaohongshu")
    if any(marker.lower() in blob for marker in _URL_BLOCKS.get("note_blocked_url") or []):
        raise AppError(
            "crawler.blocked",
            "笔记暂时无法浏览（缺少 xsec_token 或风控）",
        )


def _is_search_notes_url(url: str) -> bool:
    blob = (url or "").lower()
    return any(marker.lower() in blob for marker in _SEARCH_API_MARKERS)


def _is_feed_url(url: str) -> bool:
    blob = (url or "").lower()
    return any(marker.lower() in blob for marker in _FEED_API_MARKERS)


def _is_comment_url(url: str) -> bool:
    blob = (url or "").lower()
    contains = _COMMENT_MATCHERS.get("contains") or []
    excludes = _COMMENT_MATCHERS.get("excludes") or []
    if not contains:
        return False
    if not all(marker.lower() in blob for marker in contains):
        return False
    if any(marker.lower() in blob for marker in excludes):
        return False
    return True


async def _drain_comments(pending: list[Any], captured: list[dict[str, Any]]) -> None:
    """读取 comment/page 响应。"""
    from src.crawler.extraction.config import dig_first, path_list, section
    from src.crawler.sources.xiaohongshu.extractor import EXTRACT

    rows_paths = path_list(section(EXTRACT, "comment_api"), "rows")
    while pending:
        response = pending.pop(0)
        try:
            body = await response.json()
        except Exception:  # noqa: BLE001
            logger.debug("读取 comment/page body 失败", exc_info=True)
            continue
        if isinstance(body, dict):
            captured.append(body)
            rows = dig_first(body, rows_paths)
            count = len(rows) if isinstance(rows, list) else 0
            logger.info("截获 comment/page comments=%s code=%s", count, body.get("code"))


async def _with_comments(
    item: Any,
    raw_page: Any,
    *,
    comment_pending: list[Any],
    comment_bodies: list[dict[str, Any]],
) -> Any:
    """滚动评论区并截获 comment/page；失败则原样返回。"""
    from dataclasses import replace

    from src.crawler.core.types import CrawlItem

    if not isinstance(item, CrawlItem):
        return item

    try:
        await _drain_comments(comment_pending, comment_bodies)
        for _ in range(_COMMENT_ROUNDS):
            try:
                await raw_page.evaluate(SCROLL_COMMENTS_JS, comments_dom_arg())
            except Exception:  # noqa: BLE001
                logger.debug("scroll comments failed", exc_info=True)
            wait = getattr(raw_page, "wait_for_timeout", None)
            if wait is not None:
                await wait(_COMMENT_WAIT_MS)
            await _drain_comments(comment_pending, comment_bodies)
            if comments_from_captured(comment_bodies):
                break

        comments = comments_from_captured(comment_bodies)
        if not comments:
            dom_rows = await raw_page.evaluate(DOM_COMMENTS_JS, comments_dom_arg())
            if isinstance(dom_rows, list):
                for row in dom_rows:
                    if not isinstance(row, dict):
                        continue
                    content = str(row.get("content") or "").strip()
                    if not content:
                        continue
                    comments.append(
                        {
                            "author": str(row.get("author") or "").strip() or _ANON,
                            "content": content,
                            "time": None,
                            "reply": None,
                        }
                    )

        if not comments:
            logger.info("comments empty item_id=%s", item.item_id)
            return item

        merged = {**(item.raw or {}), "comments": comments}
        logger.info("comments done item_id=%s count=%s", item.item_id, len(comments))
        return replace(item, raw=merged)
    except Exception:  # noqa: BLE001
        logger.info("comments skipped item_id=%s", item.item_id, exc_info=True)
        return item


async def _drain_pending(pending: list[Any], captured: list[dict[str, Any]]) -> None:
    """把已登记的 Response 读成 JSON 写入 captured。"""
    while pending:
        response = pending.pop(0)
        try:
            body = await response.json()
        except Exception:  # noqa: BLE001
            try:
                text = await response.text()
                logger.warning(
                    "search/notes 非 JSON status=%s preview=%s",
                    getattr(response, "status", "?"),
                    (text or "")[:160],
                )
            except Exception:  # noqa: BLE001
                logger.debug("读取 search/notes body 失败", exc_info=True)
            continue
        if isinstance(body, dict):
            captured.append(body)
            logger.info(
                "截获 search/notes keys=%s code=%s",
                sorted(body.keys()),
                body.get("code"),
            )


async def _drain_feed(pending: list[Any], captured: list[dict[str, Any]]) -> None:
    """读取 feed 响应。"""
    while pending:
        response = pending.pop(0)
        try:
            body = await response.json()
        except Exception:  # noqa: BLE001
            logger.debug("读取 feed body 失败", exc_info=True)
            continue
        if isinstance(body, dict):
            captured.append(body)
            logger.info(
                "截获 feed keys=%s code=%s",
                sorted(body.keys()),
                body.get("code"),
            )


def _item_from_feed(captured: list[dict[str, Any]], note_id: str) -> Any | None:
    for body in reversed(captured):
        data = body.get("data") if isinstance(body.get("data"), dict) else body
        if not isinstance(data, dict):
            continue
        item = item_from_detail(data, note_id)
        if item.title:
            return item
    return None


def _items_from_captured(captured: list[dict[str, Any]], *, limit: int) -> list[Any]:
    for body in reversed(captured):
        data = body.get("data")
        payload = data if isinstance(data, dict) else body
        items = items_from_feeds(payload, limit=limit)
        if items:
            return items
    return []


def _captured_needs_login(captured: list[dict[str, Any]]) -> bool:
    for body in captured:
        code = body.get("code")
        msg = str(body.get("msg") or body.get("message") or "")
        if code in (-100, 401, 300011) or "登录" in msg:
            return True
    return False


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
    from src.crawler.sources.xiaohongshu.extractor import EXTRACT
    from src.crawler.extraction.config import section

    cfg = section(EXTRACT, "detail_params")
    meta_token = str(cfg.get("meta_token_key") or "")
    meta_source = str(cfg.get("meta_source_key") or "")
    token = str(ctx.meta.get(meta_token) or "").strip()
    if not token:
        return None
    source = str(ctx.meta.get(meta_source) or "").strip() or None
    return detail_goto_params(token=token, source=source)


def _normalize_limit(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return _DEFAULT_LIMIT
    return min(MAX_LIMIT, max(1, n))
