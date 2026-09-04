"""采集用 Browser 入口：把 BrowserPool 收成 acquire / release / stop。

职责：
    对 Crawler / Tool 隐藏池细节，统一申请与归还 Browser/Context 槽位。
    不在本文件启动第二套 Runtime。

设计说明：
    - 共享实例走 ``get_browser_manager()``；风控恢复自建 Manager + start/stop
    - Crawler 只拿返回的 BrowserPort，禁止自己 launch/close Camoufox
    - 调度、并发上限、空闲回收在 BrowserPool；Camoufox adapter 负责真正开页

使用示例：
    port = await get_browser_manager().acquire()
    try:
        page = await port.open(...)
    finally:
        await page.close()
        await get_browser_manager().release(port)
"""

from __future__ import annotations

import logging

from src.browser.pool import BrowserPool, PooledPort
from src.browser.port import BrowserPort, LaunchOptions

logger = logging.getLogger("dingda.browser.manager")

_shared: BrowserManager | None = None


class BrowserManager:
    """进程内 BrowserPool 门面。"""

    def __init__(
        self,
        engine: str = "camoufox",
        *,
        idle_timeout_s: float | None = None,
        max_browsers: int | None = None,
        max_contexts_per_browser: int | None = None,
    ) -> None:
        self._pool = BrowserPool(
            engine,
            max_browsers=max_browsers,
            max_contexts_per_browser=max_contexts_per_browser,
            idle_timeout_s=idle_timeout_s,
        )

    @property
    def engine(self) -> str:
        return self._pool.engine

    @property
    def pool(self) -> BrowserPool:
        """底层池（扩展/测试）。"""
        return self._pool

    @property
    def port(self) -> BrowserPort:
        """已就绪的一台；未启动则报错。"""
        inst = self._pool.peek()
        if inst is None:
            raise RuntimeError("浏览器尚未启动")
        return PooledPort(self._pool, inst)

    async def start(self, options: LaunchOptions | None = None) -> BrowserPort:
        """预热并钉住一台 Browser（风控恢复 / 测试）。采集请用 acquire。"""
        return await self._pool.ensure_pinned(options)

    async def acquire(self, options: LaunchOptions | None = None) -> BrowserPort:
        """向池申请一个任务槽位（Browser + 一个 Context 配额）。"""
        return await self._pool.acquire(options)

    async def release(self, port: BrowserPort | None = None) -> None:
        """归还 acquire 拿到的 Port；未传 Port 则忽略。"""
        if port is None:
            logger.info("归还时未传入 Port，已跳过")
            return
        await self._pool.release(port)

    async def stop(self) -> None:
        """关闭池内全部 Browser。"""
        await self._pool.stop()


def get_browser_manager() -> BrowserManager:
    """采集用的进程级单例。"""
    global _shared
    if _shared is None:
        _shared = BrowserManager()
        logger.info(
            "浏览器管理器已创建 engine=%s max_browsers=%s max_contexts=%s idle_timeout=%ss",
            _shared.engine,
            _shared.pool.max_browsers,
            _shared.pool.max_contexts_per_browser,
            int(_shared.pool.idle_timeout_s),
        )
    return _shared
