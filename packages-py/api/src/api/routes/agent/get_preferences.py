"""Agent 偏好读取端点。

职责：
    读取默认 Agent 与各 Agent 默认模型，供设置页首屏。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from contracts.agent import AgentPreferencesView
from infrastructure.db import settings as settings_repo

logger = logging.getLogger("dingda.api.agent")

router = APIRouter()


@router.get("/preferences", response_model=AgentPreferencesView)
def get_agent_preferences() -> AgentPreferencesView:
    """读取默认 Agent 与各 Agent 默认模型。"""
    default_agent_id = settings_repo.get_default_agent_id()
    default_models = settings_repo.get_default_models()
    logger.info(
        "已读取 Agent 偏好 default_agent=%s models=%s",
        default_agent_id,
        default_models,
    )
    return AgentPreferencesView(
        default_agent_id=default_agent_id,
        default_models=default_models,
    )
