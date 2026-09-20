"""浏览器会话编排：取一台浏览器 → 建 Crawler → 跑一步 → 归还。

职责：
    把「借一台浏览器、建 Crawler、跑抓取、归还浏览器」收成一处，
    并把直播帧接到 ``RunContext.emit_frame``。

设计说明：
    - 「有没有空闲浏览器、没有就起一台、池满就排队」的判定在 ``BrowserPool``
      （``browser/manager.py``）。本模块只做编排，绝不自己 launch 浏览器。
    - **一次会话只 acquire 一次**：同一次运行里的列表与逐条详情走同一台浏览器、
      同一个 Context 策略，用户不会看到浏览器反复启停。
    - **不做登录恢复**：撞到账号失效由工具原样回报，交给主编排查扫码 —— 恢复是
      编排层的决定，不是会话层的。
"""

from __future__ import annotations

import logging
import os
import uuid
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from browser.manager import BrowserManager, get_browser_manager
from contracts.browser_port import LaunchOptions
from crawler.core.base import BrowserSessionOptions
from crawler.core.live import META_LIVE_CALLBACK, META_LIVE_ENABLED
from crawler.core.types import CrawlContext
from crawler.registry import cookies_for, create_crawler

from agent.context import RunContext

logger = logging.getLogger("dingda.agent.session")

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def headless() -> bool:
    """采集浏览器是否无头。

    正常采集一律无头；只有人工排障（想亲眼看到页面打开到哪一步）才认
    ``DINGDA_CRAWL_HEADED``。与风控那个有头窗口无关，那是另一台独立浏览器。
    """
    return (os.getenv("DINGDA_CRAWL_HEADED", "") or "").strip().lower() not in _TRUTHY


@dataclass(frozen=True)
class CrawlSession:
    """一次抓取会话：一台浏览器 + 已建好的 Crawler + 共享 meta。"""

    platform: str
    crawler: Any
    task_id: str
    live_meta: dict[str, Any]

    def ctx(self, **extra: Any) -> CrawlContext:
        """给本会话某一步造 ``CrawlContext``；``extra`` 覆盖同名 meta。"""
        return CrawlContext(task_id=self.task_id, meta={**self.live_meta, **extra})


@asynccontextmanager
async def crawl_session(
    platform: str,
    *,
    ctx: RunContext,
    cookie: str | None = None,
    proxy_url: str | None = None,
    extra_meta: Mapping[str, Any] | None = None,
    headless: bool | None = None,
    dedicated: bool = False,
) -> AsyncIterator[CrawlSession]:
    """取一台空闲浏览器（没有就起一台），跑完归还。

    ``ctx.live_enabled`` 为真时才挂直播回调；没有回调时抓取照跑，只是没画面。
    ``dedicated`` 用于人工风控这类短任务：用独立单槽池，退出时立刻关浏览器。
    """
    manager = (
        BrowserManager(max_browsers=1, max_contexts_per_browser=1)
        if dedicated
        else get_browser_manager()
    )
    port = await manager.acquire(LaunchOptions(headless=headless if headless is not None else _headless()))
    try:
        options = BrowserSessionOptions(
            proxy_url=proxy_url,
            cookies=cookies_for(platform, cookie),
        )
        crawler = create_crawler(platform, port, options)
        meta: dict[str, Any] = {
            "cookie": cookie or "",
            META_LIVE_ENABLED: ctx.live_enabled,
        }
        if extra_meta:
            meta.update(extra_meta)
        if ctx.live_enabled:
            meta[META_LIVE_CALLBACK] = _frame_sink(ctx)
        session = CrawlSession(
            platform=platform,
            crawler=crawler,
            task_id=ctx.task_id or f"task-{uuid.uuid4().hex[:12]}",
            live_meta=meta,
        )
        logger.info(
            "抓取会话开始 platform=%s task=%s live=%s",
            platform,
            session.task_id,
            ctx.live_enabled,
        )
        yield session
    finally:
        try:
            await manager.release(port)
        finally:
            if dedicated:
                await manager.stop()
        logger.info("抓取会话结束 platform=%s dedicated=%s", platform, dedicated)


def _headless() -> bool:
    """模块内别名，避免与参数同名时遮蔽。"""
    return headless()


def _frame_sink(ctx: RunContext):
    """把 crawler 的帧 dict 转成 ``browserFrame`` 事件。"""

    async def on_frame(frame: dict[str, Any]) -> None:
        await ctx.emit_frame(
            url=str(frame.get("url") or ""),
            title=str(frame.get("title") or ""),
            hint=frame.get("hint"),
            mime=str(frame.get("mime") or "image/jpeg"),
            image_b64=str(frame.get("image_b64") or ""),
        )

    return on_frame
