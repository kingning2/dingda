"""AI 工作对话列表端点。

职责：
    按更新时间倒序返回最近工作快照的摘要（标题、状态标签）。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from contracts.agent import AgentWorkListResponse, AgentWorkSummaryView
from infrastructure.db import agent_works as works_repo

logger = logging.getLogger("dingda.api.agent")

router = APIRouter()


@router.get("/works", response_model=AgentWorkListResponse)
def list_agent_works(limit: int = 40) -> AgentWorkListResponse:
    """最近工作列表（按 updated_at 倒序）。"""
    rows = works_repo.list_works(limit=limit)
    items: list[AgentWorkSummaryView] = []
    for row in rows:
        status = row.detail.get("status") if isinstance(row.detail.get("status"), dict) else {}
        items.append(
            AgentWorkSummaryView(
                work_id=row.work_id,
                title=row.title or row.work_id,
                updated_at=row.updated_at,
                status_label=str(status.get("label") or "").strip() or None,
                status_state=str(status.get("state") or "").strip() or None,
            )
        )
    logger.info("agent works listed count=%s", len(items))
    return AgentWorkListResponse(items=items)
