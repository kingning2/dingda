"""爬取过程直播帧：截图推给调用方（HTTP SSE / Agent UI）。

职责：
    受 ``live_frame_enabled`` 开关控制；开启且提供回调时才截图推送。
    经 BrowserPort.screenshot 出 JPEG，不碰 Playwright / 平台业务。

设计说明：
    - meta["live_frame_enabled"] = True/False（默认 False，不推送）
    - meta["on_live_frame"] = async (frame: dict) -> None
    - frame: url / title / mime / image_b64 / hint

使用示例：
    ctx = CrawlContext(task_id="t1", meta={
        "live_frame_enabled": True,
        "on_live_frame": on_frame,
    })
    await emit_live_frame(ctx, page, title="闲鱼 · 露营椅")
"""

from __future__ import annotations

import asyncio
import base64
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from src.browser.port import Page
from src.crawler.core.types import CrawlContext

logger = logging.getLogger("dingda.crawler.live")

LiveFrameCallback = Callable[[dict[str, Any]], Awaitable[None] | None]

# CrawlContext.meta 键
META_LIVE_ENABLED = "live_frame_enabled"
META_LIVE_CALLBACK = "on_live_frame"

FRAME_INTERVAL_S = 1.1
# 抓完后停留，方便用户看清直播画面
LIST_DWELL_S = 2.8
DETAIL_DWELL_S = 3.2

# 可选：每帧截图前钩子（如清登录弹层）
META_BEFORE_FRAME = "on_before_live_frame"


@dataclass
class LiveFramePump:
    """后台推帧句柄。"""

    stop: asyncio.Event
    task: asyncio.Task[None] | None

    async def aclose(self) -> None:
        """停止推帧并等待任务结束。"""
        self.stop.set()
        if self.task is None:
            return
        try:
            await asyncio.wait_for(self.task, timeout=2.0)
        except (TimeoutError, asyncio.CancelledError):
            self.task.cancel()


def is_live_frame_enabled(ctx: CrawlContext) -> bool:
    """是否开启直播推帧：开关为 True 且已挂回调。"""
    if ctx.meta.get(META_LIVE_ENABLED) is not True:
        return False
    return _callback(ctx) is not None


def _callback(ctx: CrawlContext) -> LiveFrameCallback | None:
    cb = ctx.meta.get(META_LIVE_CALLBACK)
    return cb if callable(cb) else None


def _before_frame(ctx: CrawlContext) -> LiveFrameCallback | None:
    cb = ctx.meta.get(META_BEFORE_FRAME)
    return cb if callable(cb) else None


async def emit_live_frame(
    ctx: CrawlContext,
    page: Page,
    *,
    title: str,
    hint: str | None = None,
    enabled: bool | None = None,
) -> None:
    """拍一帧推给 on_live_frame。

    enabled:
        - None：看 ctx.meta["live_frame_enabled"]
        - True / False：本次调用强制开/关（仍需有回调才推）
    """
    if enabled is False:
        return
    if enabled is None and not is_live_frame_enabled(ctx):
        return
    cb = _callback(ctx)
    if cb is None:
        return
    before = _before_frame(ctx)
    if before is not None:
        try:
            result = before({})
            if asyncio.iscoroutine(result):
                await result
        except Exception:  # noqa: BLE001
            logger.debug("before live frame failed", exc_info=True)
    try:
        raw = await page.screenshot(image_type="jpeg", quality=55)
        payload = {
            "url": page.url,
            "title": title,
            "hint": hint,
            "mime": "image/jpeg",
            "image_b64": base64.b64encode(raw).decode("ascii"),
        }
        result = cb(payload)
        if asyncio.iscoroutine(result):
            await result
    except Exception:  # noqa: BLE001 — 直播失败不打断抓取
        logger.debug("emit live frame failed", exc_info=True)


async def live_frame_pump(
    ctx: CrawlContext,
    page: Page,
    *,
    title: str,
    interval_s: float = FRAME_INTERVAL_S,
    enabled: bool | None = None,
) -> LiveFramePump:
    """后台按间隔推帧；未开启则返回空泵。"""
    stop = asyncio.Event()
    allow = enabled is True or (enabled is None and is_live_frame_enabled(ctx))
    if not allow or _callback(ctx) is None:
        return LiveFramePump(stop=stop, task=None)

    async def _loop() -> None:
        while not stop.is_set():
            await emit_live_frame(ctx, page, title=title, hint="直播中", enabled=True)
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval_s)
            except TimeoutError:
                continue

    task = asyncio.create_task(_loop(), name="crawler-live-frame-pump")
    return LiveFramePump(stop=stop, task=task)


async def dwell_for_viewer(
    ctx: CrawlContext,
    page: Page,
    *,
    title: str,
    hint: str,
    seconds: float,
) -> None:
    """直播开启时多停一会，让用户看清当前页在做什么。"""
    if seconds <= 0:
        return
    if not is_live_frame_enabled(ctx):
        return
    await emit_live_frame(ctx, page, title=title, hint=hint)
    await asyncio.sleep(seconds)
