"""FastAPI 应用工厂模块。"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.router import api_router
from src.core.config import Settings
from src.core.exceptions import register_exception_handlers
from src.core.lifespan import create_lifespan


def create_app(settings: Settings | None = None) -> FastAPI:
    """根据配置创建 FastAPI 应用实例。"""
    settings = settings or Settings.from_env()
    app = FastAPI(
        title="DingDa v2",
        version="0.1.0",
        lifespan=create_lifespan(settings),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:1420",
            "http://127.0.0.1:1420",
            "tauri://localhost",
            "https://tauri.localhost",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    register_exception_handlers(app)
    return app
