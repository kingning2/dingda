"""API 路由聚合模块。"""

from __future__ import annotations

from fastapi import APIRouter

from src.api import account, agent, bootstrap, channel, crawler, health, mcp, research, runtime

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(bootstrap.router)
api_router.include_router(runtime.router)
api_router.include_router(channel.router)
api_router.include_router(account.router)
api_router.include_router(agent.router)
api_router.include_router(crawler.router)
api_router.include_router(mcp.router)
api_router.include_router(research.router)
