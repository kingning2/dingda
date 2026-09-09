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

from src.browser.port import BrowserPort, Cookie
from src.channels.cookie_header import parse_cookie_header
from src.channels.xiaohongshu.cookies import to_browser_cookies
from src.crawler.core.base import BrowserCrawler, BrowserSessionOptions
from src.crawler.core.types import CrawlContext, CrawlResult
from src.crawler.sources.xiaohongshu.extractor import (
    DETAIL_HINT_JS,
    DETAIL_JS,
    DETAIL_READY_JS,
    DOM_DETAIL_JS,
    DOM_SEARCH_JS,
    NOTE_URL,
    PAGE_HINT_JS,
    SEARCH_JS,
    SEARCH_READY_JS,
    SEARCH_URL,
    item_from_detail,
    items_from_feeds,
)
from src.shared.errors import AppError, risk_control_error, session_expired_error

logger = logging.getLogger("dingda.crawler.xiaohongshu")

COOKIE_DOMAIN = ".xiaohongshu.com"
MAX_LIMIT = 100
_READY_TRIES = 50
# 搜索接口路径（现网多为 v1；放宽匹配避免改版漏截）
_SEARCH_API_MARKERS = (
    "api/sns/web/v1/search/notes",
    "api/sns/web/v2/search/notes",
    "/search/notes",
)


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
        pending: list[Any] = []
        seen_apis: list[str] = []
        captured: list[dict[str, Any]] = []

        def _on_response(response: Any) -> None:
            # 同步登记；body 延后 await，避免 async listener 未调度导致截获为空
            try:
                url = str(getattr(response, "url", "") or "")
                if "edith.xiaohongshu.com" in url or "/api/sns/" in url:
                    status = getattr(response, "status", "?")
                    method = getattr(getattr(response, "request", None), "method", "?")
                    path = url.split("?", 1)[0]
                    mark = f"{status} {method} {path}"
                    if mark not in seen_apis and len(seen_apis) < 40:
                        seen_apis.append(mark)
                if not _is_search_notes_url(url):
                    return
                method = getattr(getattr(response, "request", None), "method", "")
                if method not in {"GET", "POST"}:
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
            await emit_live_frame(ctx, page, title=title, hint="正在打开搜索页")
            await page.goto(
                SEARCH_URL,
                params={"keyword": query, "source": "web_explore_feed"},
            )
            await emit_live_frame(ctx, page, title=title, hint="页面已打开")
            pump = await live_frame_pump(ctx, page, title=title)
            _raise_if_blocked(page.url)

            items: list[Any] = []
            via = ""
            for _ in range(_READY_TRIES):
                await _drain_pending(pending, captured)
                if captured:
                    items = _items_from_captured(captured, limit=limit)
                    if items:
                        via = "xhr"
                        break
                    if _captured_needs_login(captured):
                        raise session_expired_error("xiaohongshu")

                ready = await raw_page.evaluate(SEARCH_READY_JS)
                if ready:
                    state_payload = await raw_page.evaluate(SEARCH_JS)
                    if isinstance(state_payload, dict):
                        items = items_from_feeds(state_payload, limit=limit)
                        if items:
                            via = "state"
                            break

                dom_payload = await raw_page.evaluate(DOM_SEARCH_JS)
                if isinstance(dom_payload, dict):
                    items = items_from_feeds(dom_payload, limit=limit)
                    if items:
                        via = "dom"
                        break

                wait = getattr(raw_page, "wait_for_timeout", None)
                if wait is not None:
                    await wait(250)

            await _drain_pending(pending, captured)
            if not items and captured:
                items = _items_from_captured(captured, limit=limit)
                if items:
                    via = "xhr"
                elif _captured_needs_login(captured):
                    raise session_expired_error("xiaohongshu")

            if not items:
                hint = await raw_page.evaluate(PAGE_HINT_JS)
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

        def _on_response(response: Any) -> None:
            try:
                url = str(getattr(response, "url", "") or "")
                if not _is_feed_url(url):
                    return
                method = getattr(getattr(response, "request", None), "method", "")
                if method not in {"GET", "POST"}:
                    return
                pending.append(response)
                logger.info(
                    "命中 feed status=%s url=%s",
                    getattr(response, "status", "?"),
                    url.split("?", 1)[0],
                )
            except Exception:  # noqa: BLE001
                logger.debug("登记 feed 响应失败", exc_info=True)

        try:
            title = f"小红书详情 · {note_id[:8]}"
            raw_page = _raw(page)
            raw_page.on("response", _on_response)
            params = _detail_params(ctx)
            if not params:
                logger.warning("detail 无 xsec_token，裸开极易 300031 item_id=%s", note_id)
            # 先打开弹层给用户看，数据可从 feed HTTP / DOM 抽
            await page.goto(f"{NOTE_URL}/{note_id}", params=params)
            await emit_live_frame(ctx, page, title=title, hint="笔记卡片已打开")
            pump = await live_frame_pump(ctx, page, title=title)
            _raise_if_blocked(page.url)

            item = None
            via = ""
            for _ in range(_READY_TRIES):
                await _drain_feed(pending, captured)
                if captured:
                    item = _item_from_feed(captured, note_id)
                    if item and item.title:
                        via = "feed"
                        break

                dom = await raw_page.evaluate(DOM_DETAIL_JS, note_id)
                if isinstance(dom, dict):
                    if dom.get("blocked"):
                        raise AppError(
                            "crawler.blocked",
                            "笔记暂时无法浏览（缺少 xsec_token 或风控）",
                        )
                    if dom.get("ready") and isinstance(dom.get("note"), dict):
                        item = item_from_detail(dom, note_id)
                        if item.title:
                            via = "dom"
                            break

                ready = await raw_page.evaluate(DETAIL_READY_JS)
                if ready:
                    payload = await raw_page.evaluate(DETAIL_JS, note_id)
                    if isinstance(payload, dict) and payload.get("note"):
                        item = item_from_detail(payload, note_id)
                        if item.title:
                            via = "state"
                            break

                wait = getattr(raw_page, "wait_for_timeout", None)
                if wait is not None:
                    await wait(250)

            await _drain_feed(pending, captured)
            if (not item or not item.title) and captured:
                item = _item_from_feed(captured, note_id)
                if item and item.title:
                    via = "feed"

            if not item or not item.title:
                hint = await raw_page.evaluate(DETAIL_HINT_JS)
                logger.warning("detail empty hint=%s captured=%s", hint, len(captured))
                if isinstance(hint, dict) and (
                    hint.get("error_code") == "300031"
                    or "300031" in str(hint.get("url") or "")
                ):
                    raise AppError(
                        "crawler.blocked",
                        "笔记暂时无法浏览，请用搜索结果里的 xsec_token 打开",
                    )
                raise AppError("crawler.extract_failed", f"未拿到笔记 {note_id} 弹层数据")

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
                "detail done item_id=%s via=%s title=%s ocr_chars=%s",
                item.item_id,
                via or "?",
                item.title[:40],
                len(str((item.raw or {}).get("ocr_text") or "")),
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
    ocr_text = ocr_image_urls(str_urls, referer=item.url or "https://www.xiaohongshu.com/")
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


def _raise_if_blocked(url: str) -> None:
    blob = (url or "").lower()
    if "website-login/captcha" in blob:
        raise risk_control_error("小红书触发安全验证")
    if "xiaohongshu.com/login" in blob:
        raise session_expired_error("xiaohongshu")
    if "error_code=300031" in blob or ("/404?" in blob and "sec_" in blob):
        raise AppError(
            "crawler.blocked",
            "笔记暂时无法浏览（缺少 xsec_token 或风控）",
        )


def _is_search_notes_url(url: str) -> bool:
    blob = (url or "").lower()
    return any(marker in blob for marker in _SEARCH_API_MARKERS)


def _is_feed_url(url: str) -> bool:
    blob = (url or "").lower()
    return "api/sns/web/v1/feed" in blob or "api/sns/web/v2/feed" in blob


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
    token = str(ctx.meta.get("xsec_token") or "").strip()
    if not token:
        return None
    # 搜索入口必须用 pc_search；pc_feed 直开仍会 300031
    source = str(ctx.meta.get("xsec_source") or "pc_search").strip() or "pc_search"
    return {"xsec_token": token, "xsec_source": source}


def _normalize_limit(value: Any) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError):
        return 20
    return min(MAX_LIMIT, max(1, n))
