"""Agent 路由域。

职责：
    聚合 agent 域各端点挂到 ``/v1/agent``；每端点一个文件。
    覆盖 AI 工作对话快照，以及产品 Agent 的 SSE 运行入口。

设计说明：
    - 对话快照落在 SQLite ``agent_works``（产品自建真相源）
    - Agent 运行在 Python ``agent``（内置 LLM + 工具循环），SSE 出事件
"""

from __future__ import annotations

from fastapi import APIRouter

from api.routes.agent import (
    get_work,
    list_works,
    put_work,
    run_work,
)

router = APIRouter(prefix="/v1/agent", tags=["agent"])
router.include_router(list_works.router)
router.include_router(get_work.router)
router.include_router(put_work.router)
router.include_router(run_work.router)
