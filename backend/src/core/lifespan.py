"""FastAPI 应用生命周期钩子。"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.adapters.bootstrap import ensure_third_party_path
from src.adapters.crawler.goofish import configure_goofish_runtime
from src.core.config import Settings
from src.core.logging import info
from src.infrastructure.db.session import init_db, shutdown_db


def create_lifespan(settings: Settings):
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        info("启动应用（轻量模式）", {"host": settings.host, "port": settings.port})
        ensure_third_party_path()
        configure_goofish_runtime()
        await init_db()
        yield
        await shutdown_db()

    return lifespan
