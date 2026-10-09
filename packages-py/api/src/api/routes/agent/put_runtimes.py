"""Agent CLI 目录写入端点。

职责：
    手动扫描完成后写入 Agent CLI 目录（含模型）。
"""

from __future__ import annotations

from fastapi import APIRouter

from contracts.agent import AgentRuntimesCatalogPutRequest, AgentRuntimesCatalogView
from core.errors import AppError
from infrastructure.db import settings as settings_repo

router = APIRouter()


@router.put("/runtimes", response_model=AgentRuntimesCatalogView)
def put_agent_runtimes_catalog(
    request: AgentRuntimesCatalogPutRequest,
) -> AgentRuntimesCatalogView:
    """手动扫描完成后写入 Agent CLI 目录（含模型）。"""
    if not isinstance(request.agents, list):
        raise AppError("agent.runtimes_invalid", "agents 必须是数组", status_code=400)
    saved = settings_repo.set_agent_runtimes_catalog(request.agents)
    return AgentRuntimesCatalogView(agents=saved)
