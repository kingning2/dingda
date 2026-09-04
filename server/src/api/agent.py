"""Agent HTTP 路由。

职责：
    暴露默认外部 Agent CLI / 默认模型偏好、扫描目录缓存，
    以及 AI 工作对话快照读写。
    不负责 PATH 探测（由 Tauri Runtime 完成；仅用户点击扫描时触发）。

设计说明：
    - 偏好与扫描目录落在 SQLite ``app_settings``
    - 对话快照落在 ``agent_works``（自建真相源；不读外部 CLI 历史文件）
    - 前端启动只读缓存；手动扫描后再 PUT ``/runtimes``
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from src.contracts.agent import (
    AgentDefaultModelPutRequest,
    AgentDefaultModelView,
    AgentDefaultPutRequest,
    AgentDefaultView,
    AgentPreferencesView,
    AgentRuntimesCatalogPutRequest,
    AgentRuntimesCatalogView,
    AgentWorkDetailResponse,
    AgentWorkPutRequest,
)
from src.infrastructure.db import agent_works as works_repo
from src.infrastructure.db import settings as settings_repo
from src.shared.errors import AppError

logger = logging.getLogger("dingda.api.agent")

router = APIRouter(prefix="/v1/agent", tags=["agent"])


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


@router.get("/default", response_model=AgentDefaultView)
def get_default_agent() -> AgentDefaultView:
    """读取当前默认 Agent id。"""
    agent_id = settings_repo.get_default_agent_id()
    logger.info("已读取默认 Agent id=%s", agent_id)
    return AgentDefaultView(default_agent_id=agent_id)


@router.put("/default", response_model=AgentDefaultView)
def put_default_agent(request: AgentDefaultPutRequest) -> AgentDefaultView:
    """把可用 Agent 设为默认并写入 SQLite。"""
    agent_id = request.agent_id.strip()
    if not agent_id:
        raise AppError("agent.invalid_id", "Agent id 不能为空", status_code=400)

    saved = settings_repo.set_default_agent_id(agent_id)
    logger.info("已保存默认 Agent id=%s", saved)
    return AgentDefaultView(default_agent_id=saved)


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


@router.get("/runtimes", response_model=AgentRuntimesCatalogView)
def get_agent_runtimes_catalog() -> AgentRuntimesCatalogView:
    """读取上次扫描落库的 Agent CLI 目录。"""
    agents = settings_repo.get_agent_runtimes_catalog()
    logger.info("已读取 Agent 扫描目录 count=%s", len(agents))
    return AgentRuntimesCatalogView(agents=agents)


@router.put("/runtimes", response_model=AgentRuntimesCatalogView)
def put_agent_runtimes_catalog(
    request: AgentRuntimesCatalogPutRequest,
) -> AgentRuntimesCatalogView:
    """手动扫描完成后写入 Agent CLI 目录（含模型）。"""
    if not isinstance(request.agents, list):
        raise AppError("agent.runtimes_invalid", "agents 必须是数组", status_code=400)
    saved = settings_repo.set_agent_runtimes_catalog(request.agents)
    return AgentRuntimesCatalogView(agents=saved)


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
