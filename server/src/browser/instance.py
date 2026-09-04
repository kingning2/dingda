"""单个 Camoufox 进程槽位。

职责：
    持有独立 BrowserPort、browser_id、占用计数与状态机。
    不对外提供给 Crawler；由 BrowserPool 调度。

设计说明：
    - 每个实例对应一次 ``create_browser`` / 一个 Firefox 进程
    - 有 ``user_data_dir`` 时即独立 profile；采集默认不持久化目录
    - 状态：starting / ready / busy / idle / closing / stopped
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from enum import StrEnum

from src.browser.port import BrowserPort, LaunchOptions

logger = logging.getLogger("dingda.browser.instance")


class BrowserState(StrEnum):
    """BrowserInstance 生命周期状态。"""

    STARTING = "starting"
    READY = "ready"
    BUSY = "busy"
    IDLE = "idle"
    CLOSING = "closing"
    STOPPED = "stopped"


class BrowserInstance:
    """池中的一台独立浏览器。"""

    def __init__(
        self,
        engine: str,
        options: LaunchOptions | None = None,
        *,
        browser_id: str | None = None,
    ) -> None:
        self.browser_id = browser_id or f"b-{uuid.uuid4().hex[:10]}"
        self.engine = engine
        self.options = options or LaunchOptions()
        self.state = BrowserState.STARTING
        self.occupancy = 0
        self.pinned = False
        self.idle_since: float | None = None
        self.idle_task: asyncio.Task[None] | None = None
        self.port: BrowserPort | None = None

    @property
    def profile(self) -> str:
        """独立 profile 路径；未启用持久化则为 none。"""
        path = self.options.user_data_dir
        return str(path) if path is not None else "none"

    def can_accept(self, max_contexts: int) -> bool:
        """已就绪且未满 Context 配额。"""
        if self.port is None:
            return False
        if self.state not in {BrowserState.IDLE, BrowserState.READY}:
            return False
        return self.occupancy < max_contexts

    def sync_state(self, max_contexts: int) -> None:
        """按占用刷新 ready / busy / idle。"""
        if self.state in {BrowserState.STARTING, BrowserState.CLOSING, BrowserState.STOPPED}:
            return
        if self.occupancy >= max_contexts:
            self.state = BrowserState.BUSY
        elif self.occupancy == 0 and not self.pinned:
            self.state = BrowserState.IDLE
        else:
            self.state = BrowserState.READY

    def cancel_idle(self) -> None:
        """取消空闲回收任务。"""
        task = self.idle_task
        self.idle_task = None
        if task is not None and not task.done():
            task.cancel()
            logger.info("空闲回收已取消 browser_id=%s", self.browser_id)

    async def launch(self, factory: Callable[[str], BrowserPort]) -> None:
        """启动独立 Camoufox 进程。"""
        self.state = BrowserState.STARTING
        started = time.perf_counter()
        # 从创建实例到 Camoufox 进程就绪
        logger.info(
            "浏览器开始启动 browser_id=%s engine=%s headless=%s profile=%s",
            self.browser_id,
            self.engine,
            self.options.headless,
            self.profile,
        )
        try:
            self.port = factory(self.engine)
            await self.port.launch(self.options)
        except Exception:
            elapsed = time.perf_counter() - started
            logger.warning(
                "浏览器启动失败 browser_id=%s elapsed=%.2fs elapsed_ms=%d",
                self.browser_id,
                elapsed,
                int(elapsed * 1000),
            )
            raise
        elapsed = time.perf_counter() - started
        self.state = BrowserState.IDLE
        logger.info(
            "浏览器启动完成 browser_id=%s state=%s elapsed=%.2fs elapsed_ms=%d",
            self.browser_id,
            self.state,
            elapsed,
            int(elapsed * 1000),
        )

    async def close(self, *, reason: str) -> None:
        """关闭本进程。"""
        self.cancel_idle()
        self.state = BrowserState.CLOSING
        port = self.port
        self.port = None
        logger.info(
            "浏览器开始关闭 browser_id=%s 原因=%s occupancy=%s",
            self.browser_id,
            reason,
            self.occupancy,
        )
        self.occupancy = 0
        self.pinned = False
        self.idle_since = None
        if port is not None:
            await port.close()
        self.state = BrowserState.STOPPED
        logger.info("浏览器已关闭 browser_id=%s state=stopped", self.browser_id)
