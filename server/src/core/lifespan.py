"""FastAPI 应用生命周期钩子。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.browser.manager import get_browser_manager
from src.browser.sync import close_sync_browser
from src.core.config import Settings
from src.core.logging import info
from src.infrastructure.db.session import init_db, shutdown_db


def create_lifespan(settings: Settings):
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        info("启动应用（轻量模式）", {"host": settings.host, "port": settings.port})
        await init_db()
        # OCR 不在启动预热：首次小红书详情时再懒加载 RapidOCR
        yield
        await get_browser_manager().stop()
        close_sync_browser()
        await shutdown_db()

    return lifespan
