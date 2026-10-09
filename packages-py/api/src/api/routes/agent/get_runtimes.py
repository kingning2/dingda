"""Agent CLI 目录读取端点。

职责：
    读取上次扫描落库的 Agent CLI 目录（含各 Agent 模型清单）。
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from contracts.agent import AgentRuntimesCatalogView
from infrastructure.db import settings as settings_repo

logger = logging.getLogger("dingda.api.agent")

router = APIRouter()


@router.get("/runtimes", response_model=AgentRuntimesCatalogView)
def get_agent_runtimes_catalog() -> AgentRuntimesCatalogView:
    """读取上次扫描落库的 Agent CLI 目录。"""
    agents = settings_repo.get_agent_runtimes_catalog()
    logger.info("已读取 Agent 扫描目录 count=%s", len(agents))
    return AgentRuntimesCatalogView(agents=agents)
