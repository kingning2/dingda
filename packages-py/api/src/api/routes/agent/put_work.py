"""AI 工作对话快照写入端点。

职责：
    覆盖写入 AI 工作对话快照；前端对话页每次落盘调用。
"""

from __future__ import annotations

from fastapi import APIRouter

from contracts.agent import AgentWorkDetailResponse, AgentWorkPutRequest
from core.errors import AppError
from infrastructure.db import agent_works as works_repo

router = APIRouter()


@router.put("/works/{work_id}", response_model=AgentWorkDetailResponse)
def put_agent_work(work_id: str, request: AgentWorkPutRequest) -> AgentWorkDetailResponse:
    """覆盖写入 AI 工作对话快照。"""
    key = work_id.strip()
    if not key:
        raise AppError("agent.work_invalid_id", "work_id 不能为空", status_code=400)
    if not isinstance(request.detail, dict) or not request.detail:
        raise AppError("agent.work_invalid_detail", "detail 不能为空", status_code=400)

    row = works_repo.upsert_work(key, request.detail)
    return AgentWorkDetailResponse(detail=row.detail)
