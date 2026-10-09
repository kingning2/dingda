"""AI 工作对话快照读取端点。

职责：
    读取已持久化的 AI 工作对话快照（完整 detail JSON）。
"""

from __future__ import annotations

from fastapi import APIRouter

from contracts.agent import AgentWorkDetailResponse
from core.errors import AppError
from infrastructure.db import agent_works as works_repo

router = APIRouter()


@router.get("/works/{work_id}", response_model=AgentWorkDetailResponse)
def get_agent_work(work_id: str) -> AgentWorkDetailResponse:
    """读取已持久化的 AI 工作对话快照。"""
    key = work_id.strip()
    if not key:
        raise AppError("agent.work_invalid_id", "work_id 不能为空", status_code=400)
    row = works_repo.get_work(key)
    if not row:
        raise AppError("agent.work_not_found", "工作对话不存在", status_code=404)
    return AgentWorkDetailResponse(detail=row.detail)
