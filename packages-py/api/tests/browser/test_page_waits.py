"""PlaywrightPage 等待原语与事件层单测（不启浏览器）。

覆盖三条硬约定：
1. 等待原语超时一律返回 False/None，**不抛异常**——风控页永远等不到正常元素，
   抛异常会把「被拦」误报成「抽取失败」。
2. 事件负载必须归一化成 ``PageEventInfo``，不把引擎对象漏给调用方。
3. 事件日志与订阅解耦：没订阅也要能看见时间线，否则排查时得先改代码。
"""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from typing import Any

import pytest

from browser.page import _LOG_TEXT_LIMIT, PlaywrightPage
from contracts.browser_port import PageEvent, PageEventInfo

# 引擎侧事件名 → 平台无关事件，构造时会全部挂上日志
_ENGINE_EVENTS = (
    "framenavigating",
    "domcontentloaded",
    "load",
    "request",
    "response",
    "requestfinished",
    "requestfailed",
    "pageerror",
    "close",
)

_LOGGER = "dingda.browser.page"


class _RawPage:
    """最小 Playwright page：记录事件注册与等待调用，可按需制造超时。"""

    def __init__(self) -> None:
        self.url = "https://example.test/search"
        self.context = object()
        self.listeners: dict[str, list[Any]] = {}
        self.waits: list[tuple[str, Any]] = []
        self.timeout_on: set[str] = set()

    def on(self, name: str, handler: Any) -> None:
        self.listeners.setdefault(name, []).append(handler)

    def remove_listener(self, name: str, handler: Any) -> None:
        self.listeners.get(name, []).remove(handler)

    def emit(self, name: str, payload: Any) -> None:
        for handler in list(self.listeners.get(name, [])):
            handler(payload)

    def count(self, name: str) -> int:
        return len(self.listeners.get(name, []))

    async def wait_for_selector(self, selector: str, *, state: str, timeout: int) -> None:
        self.waits.append(("selector", selector))
        if "selector" in self.timeout_on:
            raise TimeoutError("timeout")

    async def wait_for_load_state(self, state: str, *, timeout: int) -> None:
        self.waits.append(("load_state", state))
        if "load_state" in self.timeout_on:
            raise TimeoutError("timeout")

    async def wait_for_function(
        self,
        expression: str,
        arg: Any = None,
        **kwargs: Any,
    ) -> None:
        self.waits.append(("function", expression, kwargs.get("polling")))
        if "function" in self.timeout_on:
            raise TimeoutError("timeout")

    async def wait_for_response(self, predicate: Any, *, timeout: int) -> Any:
        self.waits.append(("response", predicate))
        if "response" in self.timeout_on:
            raise TimeoutError("timeout")
        return SimpleNamespace(url="https://api.test/list")


def test_waits_return_false_on_timeout() -> None:
    async def _run() -> None:
        raw = _RawPage()
        raw.timeout_on = {"selector", "load_state", "function", "response"}
        page = PlaywrightPage(raw)

        assert await page.wait_for_selector(".card") is False
        assert await page.wait_for_load_state() is False
        assert await page.wait_for_function("() => false") is False
        assert await page.wait_for_response("/list") is None

    asyncio.run(_run())


def test_wait_for_function_polls_by_interval() -> None:
    async def _run() -> None:
        raw = _RawPage()
        page = PlaywrightPage(raw)
        await page.wait_for_function("() => true", timeout_ms=1_000)

        # 判据常要读 innerText（触发 layout），不能按帧轮询
        kind, expression, polling = raw.waits[-1]
        assert kind == "function"
        assert expression == "() => true"
        assert polling == 200

    asyncio.run(_run())


def test_wait_for_response_matches_by_substring() -> None:
    async def _run() -> None:
        raw = _RawPage()
        page = PlaywrightPage(raw)
        await page.wait_for_response("/api/list")

        predicate = raw.waits[-1][1]
        assert predicate(SimpleNamespace(url="https://h5.test/api/list?page=1")) is True
        assert predicate(SimpleNamespace(url="https://h5.test/api/other")) is False

    asyncio.run(_run())


def test_on_maps_event_name_and_normalizes_payload() -> None:
    raw = _RawPage()
    page = PlaywrightPage(raw)
    before = raw.count("response")

    got: list[PageEventInfo] = []
    off = page.on(PageEvent.RESPONSE, got.append)
    assert raw.count("response") == before + 1

    raw.emit(
        "response",
        SimpleNamespace(url="https://h5.test/api/list", status=200, method="GET"),
    )

    assert len(got) == 1
    assert got[0].event is PageEvent.RESPONSE
    assert got[0].url == "https://h5.test/api/list"
    assert got[0].status == 200

    off()
    assert raw.count("response") == before


def test_on_handler_exception_does_not_propagate() -> None:
    raw = _RawPage()
    page = PlaywrightPage(raw)

    def _boom(_: PageEventInfo) -> None:
        raise RuntimeError("handler 自己炸了")

    page.on(PageEvent.REQUEST_FAILED, _boom)
    # 处理器异常只记日志；否则会顺着 Playwright 的事件派发打断页面
    raw.emit("requestfailed", SimpleNamespace(url="https://x.test/a", failure="net::ERR"))


def test_request_failed_carries_error_and_falls_back_to_page_url() -> None:
    raw = _RawPage()
    page = PlaywrightPage(raw)
    got: list[PageEventInfo] = []
    page.on(PageEvent.REQUEST_FAILED, got.append)

    # 没有 url 的负载要回落到当前页 URL
    raw.emit("requestfailed", SimpleNamespace(failure="net::ERR_ABORTED"))
    assert got[0].url == "https://example.test/search"
    assert got[0].error == "net::ERR_ABORTED"


def test_wait_for_event_returns_none_on_timeout() -> None:
    async def _run() -> None:
        raw = _RawPage()
        page = PlaywrightPage(raw)
        before = raw.count("load")

        assert await page.wait_for_event(PageEvent.LOADED, timeout_ms=30) is None
        assert raw.count("load") == before

    asyncio.run(_run())


def test_wait_for_event_resolves_on_matching_event() -> None:
    async def _run() -> None:
        raw = _RawPage()
        page = PlaywrightPage(raw)
        before = raw.count("load")

        async def _fire() -> None:
            await asyncio.sleep(0.01)
            raw.emit("load", SimpleNamespace(url="https://example.test/search?q=t"))

        asyncio.create_task(_fire())
        info = await page.wait_for_event(PageEvent.LOADED, timeout_ms=2_000)

        assert info is not None
        assert info.event is PageEvent.LOADED
        assert "q=t" in info.url
        assert raw.count("load") == before

    asyncio.run(_run())


def test_wait_for_event_filters_by_url() -> None:
    async def _run() -> None:
        raw = _RawPage()
        page = PlaywrightPage(raw)

        async def _fire() -> None:
            await asyncio.sleep(0.01)
            raw.emit("response", SimpleNamespace(url="https://h5.test/api/other", status=200))
            raw.emit("response", SimpleNamespace(url="https://h5.test/api/list", status=200))

        asyncio.create_task(_fire())
        info = await page.wait_for_event(
            PageEvent.RESPONSE,
            url_contains="/api/list",
            timeout_ms=2_000,
        )

        assert info is not None
        assert info.url == "https://h5.test/api/list"

    asyncio.run(_run())


def test_constructor_attaches_log_for_every_event() -> None:
    raw = _RawPage()
    PlaywrightPage(raw)

    for name in _ENGINE_EVENTS:
        assert raw.count(name) == 1, name


def test_unsupported_engine_event_is_skipped() -> None:
    class _Partial(_RawPage):
        def on(self, name: str, handler: Any) -> None:
            if name == "framenavigating":
                raise ValueError("引擎太旧，没有这个事件")
            super().on(name, handler)

    raw = _Partial()
    PlaywrightPage(raw)  # 不应抛出

    assert raw.count("framenavigating") == 0
    assert raw.count("load") == 1


def test_events_are_logged_without_any_subscriber(
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw = _RawPage()
    PlaywrightPage(raw)

    caplog.set_level(logging.INFO, logger=_LOGGER)
    raw.emit("load", SimpleNamespace(url="https://example.test/list"))

    assert any("event=loaded" in msg for msg in caplog.messages)
    assert any("url=https://example.test/list" in msg for msg in caplog.messages)


def test_event_log_levels_by_kind(caplog: pytest.LogCaptureFixture) -> None:
    raw = _RawPage()
    PlaywrightPage(raw)

    caplog.set_level(logging.DEBUG, logger=_LOGGER)
    raw.emit("load", SimpleNamespace(url="https://example.test/a"))
    raw.emit("requestfailed", SimpleNamespace(url="https://x.test/b", failure="net::ERR"))
    raw.emit("response", SimpleNamespace(url="https://x.test/c", status=200))

    levels = {rec.getMessage().split("event=")[1].split()[0]: rec.levelno for rec in caplog.records}
    assert levels["loaded"] == logging.INFO
    assert levels["request_failed"] == logging.WARNING
    assert levels["response"] == logging.DEBUG


def test_high_frequency_events_are_silent_at_info_level(
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw = _RawPage()
    PlaywrightPage(raw)

    caplog.set_level(logging.INFO, logger=_LOGGER)
    raw.emit("response", SimpleNamespace(url="https://x.test/c", status=200))

    # 一次搜索几百个请求，INFO 级别下不能刷屏
    assert not any("event=response" in msg for msg in caplog.messages)


def test_long_text_is_truncated_in_log(caplog: pytest.LogCaptureFixture) -> None:
    raw = _RawPage()
    PlaywrightPage(raw)
    long_url = "https://example.test/" + "a" * (_LOG_TEXT_LIMIT * 2)

    caplog.set_level(logging.INFO, logger=_LOGGER)
    raw.emit("load", SimpleNamespace(url=long_url))

    line = next(msg for msg in caplog.messages if "event=loaded" in msg)
    assert f"…({len(long_url)} 字符)" in line
    assert len(line) < len(long_url)
