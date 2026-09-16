"""选品 Tool：抓取会话编排（一台浏览器，多步共用）。

职责：
    把「取一台浏览器 → 建 Crawler → 跑若干步 → 归还」收成一处，
    供 search / product / browse 共用，避免每个工具各自 acquire/release。

设计说明：
    - 「有没有空闲浏览器、没有就起一台、池满就排队」的判定在 BrowserPool
      （``_pick_locked`` / ``_reserve_locked``），日志分别是「复用已有浏览器」/
      「新浏览器已接入任务」/「浏览器池已满，排队等待」。本模块只做编排，
      绝不自己 launch 浏览器。
    - **一次会话只 acquire 一次**：同一次 run 里的列表与逐条详情走同一台浏览器、
      同一个 BrowserContext 策略，用户不会看到浏览器反复启停。
    - 归还只减占用、不关进程；无人使用时才由池按 idle_timeout 回收，
      所以紧接着的下一次工具调用仍会「复用已有浏览器」。
    - 不 import Playwright / Camoufox。

使用示例：
    async with crawl_session("xianyu", cookie=cookie, live_frame_enabled=True) as session:
        result = await session.crawler.search(session.ctx(limit=30), query)
        detail = await session.crawler.detail(session.ctx(), item_id)
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from browser.manager import get_browser_manager
from contracts.browser_port import LaunchOptions
from crawler.core.base import BrowserSessionOptions
from crawler.core.live import META_LIVE_CALLBACK, META_LIVE_ENABLED
from crawler.core.types import CrawlContext
from crawler.registry import cookies_for, create_crawler
from tools.headed import headless

logger = logging.getLogger("dingda.tools.session")


@dataclass(frozen=True)
class CrawlSession:
    """一次抓取会话：一台浏览器 + 已建好的 Crawler + 共享 meta。"""

    platform: str
    crawler: Any
    task_id: str
    live_meta: dict[str, Any]

    def ctx(self, **extra: Any) -> CrawlContext:
        """给本会话某一步造 CrawlContext；``extra`` 覆盖同名 meta。"""
        return CrawlContext(task_id=self.task_id, meta={**self.live_meta, **extra})


@asynccontextmanager
async def crawl_session(
    platform: str,
    *,
    cookie: str | None = None,
    proxy_url: str | None = None,
    cookie_domain: str = "",
    on_live_frame: Any | None = None,
    live_frame_enabled: bool = False,
    task_id: str | None = None,
    extra_meta: Mapping[str, Any] | None = None,
) -> AsyncIterator[CrawlSession]:
    """取一台空闲浏览器（没有就起一台），跑完归还。

    ``live_frame_enabled`` 只是「本会话允许推帧」，真正生效还需要
    ``on_live_frame`` 回调（由 registry 按 ``DINGDA_AGENT_RUN_ID`` 决定给不给）。
    """
    manager = get_browser_manager()
    port = await manager.acquire(LaunchOptions(headless=headless()))
    try:
        options = BrowserSessionOptions(
            proxy_url=proxy_url,
            cookies=cookies_for(platform, cookie),
            cookie_domain=cookie_domain,
        )
        crawler = create_crawler(platform, port, options)
        meta: dict[str, Any] = {
            "cookie": cookie or "",
            META_LIVE_ENABLED: bool(live_frame_enabled and on_live_frame),
        }
        if extra_meta:
            meta.update(extra_meta)
        if on_live_frame is not None:
            meta[META_LIVE_CALLBACK] = on_live_frame
        session = CrawlSession(
            platform=platform,
            crawler=crawler,
            task_id=task_id or f"task-{uuid.uuid4().hex[:12]}",
            live_meta=meta,
        )
        logger.info(
            "抓取会话开始 platform=%s task=%s live=%s",
            platform,
            session.task_id,
            meta[META_LIVE_ENABLED],
        )
        yield session
    finally:
        await manager.release(port)
        logger.info("抓取会话结束 platform=%s", platform)
