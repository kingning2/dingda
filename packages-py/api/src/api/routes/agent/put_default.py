"""默认 Agent 设置端点。

职责：
    把可用 Agent 设为默认并写入 SQLite。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from contracts.agent import AgentDefaultPutRequest, AgentDefaultView
from core.errors import AppError
from infrastructure.db import settings as settings_repo

logger = logging.getLogger("dingda.api.agent")

router = APIRouter()


@router.put("/default", response_model=AgentDefaultView)
def put_default_agent(request: AgentDefaultPutRequest) -> AgentDefaultView:
    """把可用 Agent 设为默认并写入 SQLite。"""
    agent_id = request.agent_id.strip()
    if not agent_id:
        raise AppError("agent.invalid_id", "Agent id 不能为空", status_code=400)

    saved = settings_repo.set_default_agent_id(agent_id)
    logger.info("已保存默认 Agent id=%s", saved)
    return AgentDefaultView(default_agent_id=saved)
