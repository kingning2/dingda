"""API 路由聚合。

职责：
    把各域路由按固定顺序挂到 ``api_router``；app.py 只 import 这一个入口。

设计说明：
    - 域内「一端点一文件」，本层只管聚合，不写端点逻辑
    - include 顺序保持与 URL 语义一致（更具体的路径不互相遮蔽）
"""

from __future__ import annotations

from fastapi import APIRouter

from api.routes import account, agent, bootstrap, channel, crawler, health, research, runtime, watch

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(bootstrap.router)
api_router.include_router(runtime.router)
api_router.include_router(channel.router)
api_router.include_router(account.router)
api_router.include_router(agent.router)
api_router.include_router(crawler.router)
api_router.include_router(research.router)
api_router.include_router(watch.router)
