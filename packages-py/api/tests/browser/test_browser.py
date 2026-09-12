"""浏览器 registry / manager / session 单测（mock Port，不启动真实浏览器）。"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar, Mapping, Sequence

import pytest

from browser.context import normalize_cookies
from browser.manager import BrowserManager
from contracts.browser_port import BrowserPort, Cookie, LaunchOptions, Page
from browser.registry import create_browser, list_engines
from browser.session import BrowserSession
from core.errors import AppError


class _FakePage(Page):
    def __init__(self) -> None:
        self.closed = False
        self._url = "about:blank"

    @property
    def url(self) -> str:
        return self._url

    async def goto(self, url: str, **kwargs: Any) -> None:
        self._url = url

    async def content(self) -> str:
        return "<html></html>"

    async def evaluate(self, expression: str, arg: Any = None) -> Any:
        return None

    async def click(self, selector: str, **kwargs: Any) -> None:
        return None

    async def fill(self, selector: str, value: str, **kwargs: Any) -> None:
        return None

    async def screenshot(self, path: Any = None) -> bytes:
        return b"png"

    async def cookies(self) -> list[Cookie]:
        return []

    async def add_cookies(self, cookies: Any, *, default_domain: str = "") -> None:
        return None

    async def close(self) -> None:
        self.closed = True


class _FakePort(BrowserPort):
    engine: ClassVar[str] = "fake"

    def __init__(self) -> None:
        self.launched = False
        self.closed = False
        self.last_open: dict[str, Any] = {}

    async def launch(self, options: LaunchOptions | None = None) -> None:
        self.launched = True

    async def open(
        self,
        *,
        proxy: str | None = None,
        fingerprint: str | None = None,
        cookies: Sequence[Cookie] | Mapping[str, str] | None = None,
        default_domain: str = "",
    ) -> Page:
        self.last_open = {
            "proxy": proxy,
            "fingerprint": fingerprint,
            "cookies": cookies,
            "default_domain": default_domain,
        }
        return _FakePage()

    async def close(self) -> None:
        self.closed = True


def test_list_engines_includes_builtin() -> None:
    engines = list_engines()
    assert "camoufox" in engines
    assert "chromium" not in engines


def test_create_browser_unknown_raises() -> None:
    with pytest.raises(AppError) as exc:
        create_browser("nope")
    assert exc.value.code == "browser.engine_unsupported"


def test_create_browser_returns_adapter() -> None:
    port = create_browser("camoufox")
    assert port.engine == "camoufox"


def test_normalize_cookies_dict_requires_domain() -> None:
    with pytest.raises(ValueError):
        normalize_cookies({"a": "1"})
    cookies = normalize_cookies({"a": "1"}, default_domain=".example.com")
    assert cookies == [Cookie(name="a", value="1", domain=".example.com")]


def test_manager_start_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakePort()

    def _factory(engine: str) -> BrowserPort:
        assert engine == "fake"
        return fake

    monkeypatch.setattr("browser.pool.create_browser", _factory)

    async def _run() -> None:
        manager = BrowserManager(engine="fake")
        port = await manager.start()
        assert fake.launched
        assert getattr(port, "browser_id", "")
        await manager.stop()
        assert fake.closed

    asyncio.run(_run())


def test_pool_reuses_then_idle_recycle(monkeypatch: pytest.MonkeyPatch) -> None:
    ports: list[_FakePort] = []

    def _factory(engine: str) -> BrowserPort:
        fake = _FakePort()
        ports.append(fake)
        return fake

    monkeypatch.setattr("browser.pool.create_browser", _factory)

    async def _run() -> None:
        manager = BrowserManager(
            engine="fake",
            idle_timeout_s=0.05,
            max_browsers=3,
            max_contexts_per_browser=5,
        )
        first = await manager.acquire()
        second = await manager.acquire()
        assert first.browser_id == second.browser_id
        assert len(ports) == 1
        await manager.release(first)
        await manager.release(second)
        await asyncio.sleep(0.2)
        assert ports[0].closed
        third = await manager.acquire()
        assert third.browser_id != first.browser_id
        assert len(ports) == 2
        await manager.release(third)
        await manager.stop()

    asyncio.run(_run())


def test_pool_scales_to_second_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    ports: list[_FakePort] = []

    def _factory(engine: str) -> BrowserPort:
        fake = _FakePort()
        ports.append(fake)
        return fake

    monkeypatch.setattr("browser.pool.create_browser", _factory)

    async def _run() -> None:
        manager = BrowserManager(
            engine="fake",
            idle_timeout_s=30,
            max_browsers=3,
            max_contexts_per_browser=1,
        )
        first = await manager.acquire()
        second = await manager.acquire()
        assert first.browser_id != second.browser_id
        assert len(ports) == 2
        await manager.release(first)
        await manager.release(second)
        await manager.stop()

    asyncio.run(_run())


def test_pool_waits_when_at_capacity(monkeypatch: pytest.MonkeyPatch) -> None:
    def _factory(engine: str) -> BrowserPort:
        return _FakePort()

    monkeypatch.setattr("browser.pool.create_browser", _factory)

    async def _run() -> None:
        manager = BrowserManager(
            engine="fake",
            idle_timeout_s=30,
            max_browsers=1,
            max_contexts_per_browser=1,
        )
        held = await manager.acquire()
        got: list[str] = []

        async def _waiter() -> None:
            port = await manager.acquire()
            got.append(port.browser_id)
            await manager.release(port)

        task = asyncio.create_task(_waiter())
        await asyncio.sleep(0.05)
        assert not task.done()
        await manager.release(held)
        await asyncio.wait_for(task, timeout=1)
        assert got == [held.browser_id]
        await manager.stop()

    asyncio.run(_run())


def test_pool_launch_failure_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"n": 0}

    def _factory(engine: str) -> BrowserPort:
        calls["n"] += 1
        fake = _FakePort()
        if calls["n"] == 1:

            async def _boom(options: LaunchOptions | None = None) -> None:
                raise RuntimeError("launch failed")

            fake.launch = _boom  # type: ignore[method-assign]
        return fake

    monkeypatch.setattr("browser.pool.create_browser", _factory)

    async def _run() -> None:
        manager = BrowserManager(engine="fake", idle_timeout_s=30, max_browsers=2)
        port = await manager.acquire()
        assert calls["n"] == 2
        await manager.release(port)
        await manager.stop()

    asyncio.run(_run())


def test_pool_open_failure_retires_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    ports: list[_FakePort] = []

    def _factory(engine: str) -> BrowserPort:
        fake = _FakePort()
        if not ports:

            async def _dead(**kwargs: object) -> Page:
                raise RuntimeError("Target closed")

            fake.open = _dead  # type: ignore[method-assign]
        ports.append(fake)
        return fake

    monkeypatch.setattr("browser.pool.create_browser", _factory)

    async def _run() -> None:
        manager = BrowserManager(engine="fake", idle_timeout_s=30, max_browsers=3)
        first = await manager.acquire()
        with pytest.raises(RuntimeError, match="Target closed"):
            await first.open()
        second = await manager.acquire()
        assert second.browser_id != first.browser_id
        await manager.release(first)
        await manager.release(second)
        await manager.stop()

    asyncio.run(_run())


def test_session_opens_and_closes() -> None:
    async def _run() -> None:
        port = _FakePort()
        async with BrowserSession(port) as page:
            assert isinstance(page, _FakePage)
            assert not page.closed
        assert page.closed

    asyncio.run(_run())


def test_sync_headless_reuses_browser_process(monkeypatch: pytest.MonkeyPatch) -> None:
    from browser import sync as syn

    launches = {"n": 0}
    closed_pages: list[bool] = []

    class _FakePage:
        def close(self) -> None:
            closed_pages.append(True)

    class _FakeContext:
        def new_page(self) -> _FakePage:
            return _FakePage()

        def add_cookies(self, cookies: object) -> None:
            return None

        def close(self) -> None:
            return None

    class _FakeBrowser:
        def new_context(self) -> _FakeContext:
            return _FakeContext()

    def _launch(self: object, *, headless: bool) -> None:
        launches["n"] += 1
        holder = syn._holder
        holder._cm = type("CM", (), {"__exit__": lambda *a: None})()
        holder._browser = _FakeBrowser()

    syn._holder = syn._SyncBrowserHolder()
    monkeypatch.setattr(syn._SyncBrowserHolder, "_launch", _launch)

    def _once() -> None:
        with syn.sync_headless_page():
            pass

    syn.run_on_sync_browser(_once)
    syn.run_on_sync_browser(_once)
    assert launches["n"] == 1
    assert closed_pages == [True, True]
    syn.close_sync_browser()
