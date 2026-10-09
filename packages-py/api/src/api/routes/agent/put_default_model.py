"""Agent 默认模型设置端点。

职责：
    写入某 Agent 的默认模型并返回全量映射。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from contracts.agent import AgentDefaultModelPutRequest, AgentDefaultModelView
from core.errors import AppError
from infrastructure.db import settings as settings_repo

logger = logging.getLogger("dingda.api.agent")

router = APIRouter()


@router.put("/default-model", response_model=AgentDefaultModelView)
def put_default_model(request: AgentDefaultModelPutRequest) -> AgentDefaultModelView:
    """写入某 Agent 的默认模型。"""
    agent_id = request.agent_id.strip()
    model_id = request.model_id.strip()
    if not agent_id:
        raise AppError("agent.invalid_id", "Agent id 不能为空", status_code=400)
    if not model_id:
        raise AppError("agent.invalid_model", "模型 id 不能为空", status_code=400)

    mapping = settings_repo.set_default_model(agent_id, model_id)
    logger.info("已保存默认模型 agent=%s model=%s", agent_id, model_id)
    return AgentDefaultModelView(
        agent_id=agent_id,
        model_id=model_id,
        default_models=mapping,
    )
