"""Channel 扫码线程同步开页：与 async BrowserPort 共用 Cookie 契约，不直连 adapters。

职责：
    给扫码 / 探活提供同步 Playwright 页。Camoufox 只在专用线程里启动和操作，
    任务间复用进程；每次独立 Context；空闲超时再关。

设计说明：
    - Playwright 同步 API 不能跨线程复用同一 Browser（greenlet）
    - 探活、扫码、续期都排队进同一条 ``dingda-sync-browser`` 线程
    - Crawler 仍走 async Manager；空闲超时共用 ``DINGDA_BROWSER_IDLE_SECONDS``
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from concurrent.futures import Future
from contextlib import contextmanager
from typing import Any, Callable, Iterator, Sequence, TypeVar

from src.browser.context import cookies_to_playwright
from src.browser.pool import pool_idle_timeout_s
from src.browser.port import Cookie

logger = logging.getLogger("dingda.browser.sync")

T = TypeVar("T")


def _require_camoufox() -> None:
    try:
        import camoufox  # noqa: F401
    except ImportError as exc:
        raise ImportError("未安装 camoufox，请执行：uv sync") from exc


class _SyncBrowserHolder:
    """扫码专用线程上的单 Camoufox 进程。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cm: Any | None = None
        self._browser: Any | None = None
        self._in_use = 0
        self._idle: threading.Timer | None = None

    def checkout(self, *, headless: bool) -> Any:
        """拿到已启动的 browser；必要时现场启动。"""
        with self._lock:
            self._cancel_idle()
            if self._browser is None:
                self._launch(headless=headless)
            else:
                logger.info("复用同步浏览器进程 in_use=%s", self._in_use)
            self._in_use += 1
            return self._browser

    def release(self) -> None:
        """归还一次占用；无人使用则开始空闲倒计时。"""
        with self._lock:
            if self._in_use > 0:
                self._in_use -= 1
            logger.info("同步浏览器归还槽位 in_use=%s", self._in_use)
            if self._in_use == 0 and self._browser is not None:
                timeout = pool_idle_timeout_s()
                self._idle = threading.Timer(timeout, self._request_idle_close)
                self._idle.daemon = True
                self._idle.start()
                logger.info("同步浏览器开始空闲倒计时 timeout=%ss", int(timeout))

    def close(self) -> None:
        """在专用线程上关闭 Camoufox。"""
        with self._lock:
            self._close_locked(reason="主动关闭")

    def _launch(self, *, headless: bool) -> None:
        _require_camoufox()
        from camoufox.addons import DefaultAddons
        from camoufox.sync_api import Camoufox

        started = time.perf_counter()
        logger.info("同步浏览器开始启动 headless=%s", headless)
        from src.browser.camoufox_bin import require_camoufox_exe

        self._cm = Camoufox(
            headless=headless,
            humanize=False,
            locale="zh-CN",
            i_know_what_im_doing=True,
            exclude_addons=[DefaultAddons.UBO],
            executable_path=str(require_camoufox_exe()),
        )
        self._browser = self._cm.__enter__()
        elapsed = time.perf_counter() - started
        logger.info(
            "同步浏览器启动完成 elapsed=%.2fs elapsed_ms=%d",
            elapsed,
            int(elapsed * 1000),
        )

    def _cancel_idle(self) -> None:
        timer = self._idle
        self._idle = None
        if timer is not None:
            timer.cancel()

    def _request_idle_close(self) -> None:
        # Timer 不在 Camoufox 线程，关进程必须丢回专用线程
        submit_on_sync_browser(self._idle_close)

    def _idle_close(self) -> None:
        with self._lock:
            if self._in_use > 0:
                return
            self._close_locked(reason="空闲回收")

    def _close_locked(self, *, reason: str) -> None:
        self._cancel_idle()
        cm = self._cm
        self._cm = None
        self._browser = None
        self._in_use = 0
        if cm is None:
            return
        logger.info("同步浏览器开始关闭 原因=%s", reason)
        cm.__exit__(None, None, None)
        logger.info("同步浏览器已关闭")


class _SyncBrowserWorker:
    """所有同步 Playwright 调用都进这一条线程。"""

    def __init__(self) -> None:
        self._queue: queue.Queue[tuple[str, Callable[[], Any] | None, Future[Any] | None]] = (
            queue.Queue()
        )
        self._thread: threading.Thread | None = None
        self._boot = threading.Lock()

    def on_worker(self) -> bool:
        thread = self._thread
        return thread is not None and threading.current_thread() is thread

    def run(self, fn: Callable[[], T]) -> T:
        """在专用线程执行并等待结果。"""
        self._ensure()
        if self.on_worker():
            return fn()
        future: Future[T] = Future()
        self._queue.put(("job", fn, future))
        return future.result()

    def submit(self, fn: Callable[[], None]) -> None:
        """在专用线程排队执行，不等待。"""
        self._ensure()
        if self.on_worker():
            fn()
            return
        self._queue.put(("job", fn, None))

    def shutdown(self) -> None:
        """关掉 Camoufox 并结束专用线程。"""
        with self._boot:
            thread = self._thread
            if thread is None or not thread.is_alive():
                return
            self._queue.put(("stop", None, None))
        thread.join(timeout=20)
        with self._boot:
            if self._thread is thread:
                self._thread = None

    def _ensure(self) -> None:
        with self._boot:
            if self._thread is not None and self._thread.is_alive():
                return
            self._thread = threading.Thread(
                target=self._loop,
                name="dingda-sync-browser",
                daemon=True,
            )
            self._thread.start()
            logger.info("同步浏览器线程已启动")

    def _loop(self) -> None:
        while True:
            kind, fn, future = self._queue.get()
            if kind == "stop":
                _holder.close()
                return
            assert fn is not None
            try:
                result = fn()
                if future is not None:
                    future.set_result(result)
            except Exception as exc:
                if future is not None:
                    future.set_exception(exc)
                else:
                    logger.exception("同步浏览器后台任务失败")


_holder = _SyncBrowserHolder()
_worker = _SyncBrowserWorker()


def run_on_sync_browser(fn: Callable[[], T]) -> T:
    """把探活/续期整段丢到 Camoufox 专用线程执行。"""
    return _worker.run(fn)


def submit_on_sync_browser(fn: Callable[[], None]) -> None:
    """把扫码长任务丢到 Camoufox 专用线程，立即返回。"""
    _worker.submit(fn)


@contextmanager
def sync_headless_page(
    *,
    cookies: Sequence[Cookie] | None = None,
    headless: bool = True,
) -> Iterator[object]:
    """打开独立 Context 的一页；必须在专用线程里调用。"""
    if not _worker.on_worker():
        raise RuntimeError("sync_headless_page 必须在同步浏览器线程中调用")
    browser = _holder.checkout(headless=headless)
    context = browser.new_context()
    page = context.new_page()
    if cookies:
        context.add_cookies(cookies_to_playwright(cookies))
    logger.info("同步任务页已打开 cookies=%s", bool(cookies))
    try:
        yield page
    finally:
        try:
            page.close()
        finally:
            context.close()
            logger.info("同步任务页已关闭，浏览器进程保留")
            _holder.release()


def close_sync_browser() -> None:
    """Server 退出时关闭扫码用的同步 Camoufox。"""
    _worker.shutdown()
