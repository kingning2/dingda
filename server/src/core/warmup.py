"""后端渐进式预热：先响应壳层探活，再后台加载 DB。"""

from __future__ import annotations

import asyncio
from enum import StrEnum

from src.core.logging import info
from src.domains.account.token_scheduler import schedule_xianyu_token_scheduler
from src.infrastructure.db.session import init_db

_lock = asyncio.Lock()
_phase = "shell"
_warm_task: asyncio.Task[None] | None = None


class WarmupPhase(StrEnum):
    SHELL = "shell"
    WARMING = "warming"
    READY = "ready"


def current_phase() -> str:
    return _phase


def schedule_warmup() -> None:
    """在事件循环中触发后台预热（幂等）。"""
    global _warm_task

    if _phase == WarmupPhase.READY:
        return

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    if _warm_task is not None and not _warm_task.done():
        return

    _warm_task = loop.create_task(_run_warmup(), name="dingda-warmup")


async def ensure_warmed() -> None:
    """需要完整后端能力的路由在入口处 await。"""
    if _phase == WarmupPhase.READY:
        return
    await _run_warmup()


async def _run_warmup() -> None:
    global _phase

    if _phase == WarmupPhase.READY:
        return

    async with _lock:
        if _phase == WarmupPhase.READY:
            return

        _phase = WarmupPhase.WARMING
        info("后端预热开始")
        await init_db()
        _phase = WarmupPhase.READY
        schedule_xianyu_token_scheduler()
        info("后端预热完成")
