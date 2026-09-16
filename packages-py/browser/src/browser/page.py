"""Playwright 兼容 Page 包装：Camoufox / Playwright adapter 共用。"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence
from urllib.parse import urlencode, urlparse, urlunparse

from browser.context import cookies_to_playwright, normalize_cookies
from contracts.browser_port import (
    Cookie,
    Page,
    PageEvent,
    PageEventInfo,
    PageEventHandler,
)
from core.errors import AppError

logger = logging.getLogger("dingda.browser.page")

# 平台无关事件名 → Playwright 事件名。
# framenavigating 在旧版 Playwright 上不存在，注册时会失败并记日志，不影响其他事件。
_EVENT_NAMES: dict[PageEvent, str] = {
    PageEvent.NAVIGATION_START: "framenavigating",
    PageEvent.DOM_READY: "domcontentloaded",
    PageEvent.LOADED: "load",
    PageEvent.REQUEST: "request",
    PageEvent.RESPONSE: "response",
    PageEvent.REQUEST_DONE: "requestfinished",
    PageEvent.REQUEST_FAILED: "requestfailed",
    PageEvent.PAGE_ERROR: "pageerror",
    PageEvent.CLOSED: "close",
}

# 事件日志级别：高频网络事件走 DEBUG（一次搜索几百个请求），
# 生命周期走 INFO（次数少、时间线价值高），错误走 WARNING（默认就该看见）。
_LOG_LEVELS: dict[PageEvent, int] = {
    PageEvent.NAVIGATION_START: logging.INFO,
    PageEvent.DOM_READY: logging.INFO,
    PageEvent.LOADED: logging.INFO,
    PageEvent.CLOSED: logging.INFO,
    PageEvent.REQUEST_FAILED: logging.WARNING,
    PageEvent.PAGE_ERROR: logging.WARNING,
    PageEvent.REQUEST: logging.DEBUG,
    PageEvent.RESPONSE: logging.DEBUG,
    PageEvent.REQUEST_DONE: logging.DEBUG,
}

# URL / 文本在日志里的截断长度：够看清接口与参数，又不至于刷满一行。
_LOG_TEXT_LIMIT = 200


class PlaywrightPage(Page):
    """把 Playwright/Camoufox 的 page 包成 BrowserPort 用的 Page。"""

    def __init__(
        self,
        page: Any,
        *,
        context: Any | None = None,
        owns_context: bool = False,
    ) -> None:
        self._page = page
        self._context = context if context is not None else page.context
        self._owns_context = owns_context
        self._closed = False
        self._attach_event_log()

    def _attach_event_log(self) -> None:
        """给每个事件挂一条统一日志，返回的取消句柄不对外暴露。

        设计说明：
            日志与「有没有人订阅」解耦——否则排查问题时得先改代码加订阅才能看见
            事件。高频网络事件走 DEBUG，生命周期走 INFO，错误走 WARNING；
            旧版引擎没有的事件（如 ``framenavigating``）跳过，不影响其余事件。
        """
        for event, name in _EVENT_NAMES.items():
            try:
                self._page.on(name, _make_logger(event, lambda: self.url))
            except Exception:  # noqa: BLE001
                logger.debug("引擎不支持事件，跳过日志挂载 event=%s", event, exc_info=True)

    @property
    def raw(self) -> Any:
        """底层 Playwright page（仅 adapter / 交互原语使用，业务禁止依赖）。"""
        return self._page

    @property
    def context(self) -> Any:
        """底层 BrowserContext（Cookie / Channel 交互原语用）。"""
        return self._context

    @property
    def url(self) -> str:
        return str(self._page.url or "")

    def on(self, event: PageEvent, handler: PageEventHandler) -> Callable[[], None]:
        """订阅页面事件；返回取消订阅函数。"""
        name = _EVENT_NAMES.get(event)
        if name is None:
            raise AppError("browser.event_unsupported", f"不支持的事件：{event}")
        listener = _make_listener(event, handler, lambda: self.url)
        try:
            self._page.on(name, listener)
        except Exception as exc:  # noqa: BLE001
            raise AppError(
                "browser.event_unsupported",
                f"当前引擎不支持事件 {event}：{exc}",
            ) from exc
        logger.debug("页面事件已订阅 event=%s", event)

        def _off() -> None:
            try:
                self._page.remove_listener(name, listener)
            except Exception:  # noqa: BLE001
                logger.debug("取消事件订阅失败 event=%s", event, exc_info=True)

        return _off

    async def wait_for_event(
        self,
        event: PageEvent,
        *,
        url_contains: str = "",
        timeout_ms: int = 15_000,
    ) -> PageEventInfo | None:
        """等首个匹配事件；超时返回 None（不抛）。"""
        loop = asyncio.get_running_loop()
        future: asyncio.Future[PageEventInfo] = loop.create_future()

        def _handler(info: PageEventInfo) -> None:
            if future.done() or (url_contains and url_contains not in info.url):
                return
            future.set_result(info)

        off = self.on(event, _handler)
        try:
            return await asyncio.wait_for(future, timeout=timeout_ms / 1000)
        except (asyncio.TimeoutError, TimeoutError):
            logger.info(
                "等待事件未发生 event=%s url_contains=%s timeout_ms=%s",
                event,
                url_contains,
                timeout_ms,
            )
            return None
        finally:
            off()

    async def goto(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        wait_until: str = "domcontentloaded",
        timeout_ms: int = 30_000,
    ) -> None:
        """打开 URL。"""
        target = _with_query(url, params)
        logger.info("页面跳转 url=%s", target)
        await self._page.goto(target, wait_until=wait_until, timeout=timeout_ms)

    async def wait_for_selector(
        self,
        selector: str,
        *,
        state: str = "visible",
        timeout_ms: int = 15_000,
    ) -> bool:
        """等选择器达到 state；超时返回 False（不抛）。"""
        try:
            await self._page.wait_for_selector(selector, state=state, timeout=timeout_ms)
            return True
        except Exception:  # noqa: BLE001
            logger.info(
                "等待选择器未达成 selector=%s state=%s timeout_ms=%s",
                selector,
                state,
                timeout_ms,
            )
            return False

    async def wait_for_load_state(
        self,
        state: str = "domcontentloaded",
        *,
        timeout_ms: int = 30_000,
    ) -> bool:
        """等加载状态；超时返回 False（不抛）。"""
        try:
            await self._page.wait_for_load_state(state, timeout=timeout_ms)
            return True
        except Exception:  # noqa: BLE001
            logger.info("等待加载状态未达成 state=%s timeout_ms=%s", state, timeout_ms)
            return False

    async def wait_for_function(
        self,
        expression: str,
        arg: Any = None,
        *,
        timeout_ms: int = 15_000,
    ) -> bool:
        """轮询 JS 表达式至真值；超时返回 False（不抛）。

        设计说明：
            显式指定 200ms 轮询而非引擎默认的每帧（raf）。判据常要读
            ``document.body.innerText`` 这类触发 layout 的全量属性，按帧跑
            等于把主线程占满，反而拖慢页面自己的渲染。
        """
        try:
            await self._page.wait_for_function(
                expression,
                arg=arg,
                polling=200,
                timeout=timeout_ms,
            )
            return True
        except Exception:  # noqa: BLE001
            logger.info("等待 JS 条件未达成 timeout_ms=%s", timeout_ms)
            return False

    async def wait_for_response(
        self,
        url_contains: str,
        *,
        timeout_ms: int = 15_000,
    ) -> Any | None:
        """等 URL 含指定片段的响应；超时返回 None（不抛）。

        用子串谓词而非 Playwright 的 URL 参数：后者是 glob 匹配，
        传 ``/api/login`` 会被当成整串模式而不是包含关系。
        """
        try:
            return await self._page.wait_for_response(
                lambda response: url_contains in str(response.url),
                timeout=timeout_ms,
            )
        except Exception:  # noqa: BLE001
            logger.info("等待响应未出现 url_contains=%s timeout_ms=%s", url_contains, timeout_ms)
            return None

    async def content(self) -> str:
        """返回 HTML。"""
        return await self._page.content()

    async def evaluate(self, expression: str, arg: Any = None) -> Any:
        """在页面执行 JS。"""
        if arg is None:
            return await self._page.evaluate(expression)
        return await self._page.evaluate(expression, arg)

    async def click(self, selector: str, *, timeout_ms: int = 10_000) -> None:
        """点击。"""
        logger.info("页面点击 selector=%s", selector)
        await self._page.click(selector, timeout=timeout_ms)

    async def fill(self, selector: str, value: str, *, timeout_ms: int = 10_000) -> None:
        """填表。"""
        logger.info("页面填表 selector=%s", selector)
        await self._page.fill(selector, value, timeout=timeout_ms)

    async def screenshot(
        self,
        path: Path | None = None,
        *,
        image_type: str = "png",
        quality: int | None = None,
    ) -> bytes:
        """截图（png / jpeg）。"""
        kind = (image_type or "png").strip().lower()
        if kind not in {"png", "jpeg"}:
            kind = "png"
        kwargs: dict[str, Any] = {"type": kind}
        if kind == "jpeg":
            kwargs["quality"] = int(quality) if quality is not None else 60
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            kwargs["path"] = str(path)
        data = await self._page.screenshot(**kwargs)
        return bytes(data)

    async def cookies(self) -> list[Cookie]:
        """导出 Cookie。"""
        raw = await self._context.cookies()
        return [
            Cookie(
                name=str(item.get("name") or ""),
                value=str(item.get("value") or ""),
                domain=str(item.get("domain") or ""),
                path=str(item.get("path") or "/"),
                expires=item.get("expires"),
                http_only=bool(item.get("httpOnly", False)),
                secure=bool(item.get("secure", False)),
                same_site=str(item.get("sameSite") or "Lax"),
            )
            for item in raw
            if item.get("name") and item.get("value")
        ]

    async def add_cookies(
        self,
        cookies: Sequence[Cookie] | Mapping[str, str],
        *,
        default_domain: str = "",
    ) -> None:
        """注入 Cookie。"""
        normalized = normalize_cookies(cookies, default_domain=default_domain)
        payload = cookies_to_playwright(normalized)
        if not payload:
            return
        await self._context.add_cookies(payload)
        logger.info("页面已注入 Cookie count=%s", len(payload))

    async def close(self) -> None:
        """关闭页；若独占 context 则一并关闭。"""
        if self._closed:
            return
        self._closed = True
        logger.info("关闭页面 url=%s", self.url)
        try:
            await self._page.close()
        finally:
            if self._owns_context and self._context is not None:
                await self._context.close()


def _with_query(url: str, params: Mapping[str, str] | None) -> str:
    if not params:
        return url
    parsed = urlparse(url)
    query = urlencode(dict(params))
    if parsed.query:
        query = f"{parsed.query}&{query}"
    return urlunparse(parsed._replace(query=query))


def _make_logger(event: PageEvent, current_url: Callable[[], str]) -> Callable[..., None]:
    """统一的事件日志；未开启对应级别时零开销（不构造字符串）。"""

    level = _LOG_LEVELS.get(event, logging.DEBUG)

    def _listener(*args: Any) -> None:
        if not logger.isEnabledFor(level):
            return
        payload = args[0] if args else None
        try:
            logger.log(
                level,
                "页面事件 %s",
                _log_line(event, _event_info(event, payload, current_url())),
            )
        except Exception:  # noqa: BLE001
            logger.debug("事件日志失败 event=%s", event, exc_info=True)

    return _listener


def _log_line(event: PageEvent, info: PageEventInfo) -> str:
    """一行式事件描述；字段顺序固定，便于 grep 与按字段过滤。"""
    parts = [f"event={event}"]
    if info.url:
        parts.append(f"url={_short(info.url)}")
    if info.method:
        parts.append(f"method={info.method}")
    if info.status:
        parts.append(f"status={info.status}")
    if info.resource_type:
        parts.append(f"type={info.resource_type}")
    if info.error:
        parts.append(f"error={_short(info.error)}")
    if info.message:
        parts.append(f"message={_short(info.message)}")
    return " ".join(parts)


def _short(text: str) -> str:
    """超长文本截断，避免单条日志刷满屏幕（末尾标注原始长度）。"""
    if len(text) <= _LOG_TEXT_LIMIT:
        return text
    return f"{text[:_LOG_TEXT_LIMIT]}…({len(text)} 字符)"


def _make_listener(
    event: PageEvent,
    handler: PageEventHandler,
    current_url: Callable[[], str],
) -> Callable[..., None]:
    """把引擎负载归一化后转交订阅者；处理器异常只记日志，不打断页面。"""

    def _listener(*args: Any) -> None:
        payload = args[0] if args else None
        try:
            handler(_event_info(event, payload, current_url()))
        except Exception:  # noqa: BLE001
            logger.exception("页面事件处理器异常 event=%s", event)

    return _listener


def _event_info(event: PageEvent, payload: Any, fallback_url: str) -> PageEventInfo:
    """引擎负载 → ``PageEventInfo``。

    各事件负载类型不同（Request / Response / Page / Frame / Error），
    这里只取它们的共有字段，缺什么留空，避免把引擎类型漏给调用方。
    """
    url = str(getattr(payload, "url", "") or fallback_url or "")
    method = str(getattr(payload, "method", "") or "")
    status = getattr(payload, "status", 0)
    failure = getattr(payload, "failure", None)
    message = str(getattr(payload, "message", "") or "")
    if event is PageEvent.PAGE_ERROR and not message:
        message = str(payload or "")
    return PageEventInfo(
        event=event,
        url=url,
        method=method,
        status=int(status) if isinstance(status, int) else 0,
        resource_type=str(getattr(payload, "resource_type", "") or ""),
        error=str(failure) if failure else "",
        message=message,
    )
