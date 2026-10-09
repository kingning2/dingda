"""默认 Agent 读取端点。

职责：
    读取当前默认 Agent id。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from contracts.agent import AgentDefaultView
from infrastructure.db import settings as settings_repo

logger = logging.getLogger("dingda.api.agent")

router = APIRouter()


@router.get("/default", response_model=AgentDefaultView)
def get_default_agent() -> AgentDefaultView:
    """读取当前默认 Agent id。"""
    agent_id = settings_repo.get_default_agent_id()
    logger.info("已读取默认 Agent id=%s", agent_id)
    return AgentDefaultView(default_agent_id=agent_id)
