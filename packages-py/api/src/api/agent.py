"""Agent HTTP 路由。

职责：
    暴露默认外部 Agent CLI / 默认模型偏好、扫描目录缓存，
    AI 工作对话快照读写，以及产品 Agent / 外部 CLI 的 SSE 运行入口。

设计说明：
    - 偏好与扫描目录落在 SQLite ``app_settings``
    - 对话快照落在 ``agent_works``
    - CLI 启动在 Python ``cli``，不再经 Tauri spawn
    - PATH 探测/下载仍可由 Tauri 完成；运行一律走本模块
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent.core.agent import AgentService
from cli.live import hub as live_hub
from cli.spawn import cancel_run, run_cli
from cli.steps import page_from_live_frame
from contracts.agent import (
    AgentDefaultModelPutRequest,
    AgentDefaultModelView,
    AgentDefaultPutRequest,
    AgentDefaultView,
    AgentPreferencesView,
    AgentRuntimesCatalogPutRequest,
    AgentRuntimesCatalogView,
    AgentWorkDetailResponse,
    AgentWorkListResponse,
    AgentWorkPutRequest,
    AgentWorkSummaryView,
)
from infrastructure.db import agent_works as works_repo
from infrastructure.db import settings as settings_repo
from core.errors import AppError

logger = logging.getLogger("dingda.api.agent")

router = APIRouter(prefix="/v1/agent", tags=["agent"])


class AgentWorkRunRequest(BaseModel):
    """产品 Agent 运行请求。"""

    prompt: str = Field(description="用户原文")
    run_id: str | None = None


class AgentRuntimeRunRequest(BaseModel):
    """外部 CLI Runtime 运行请求。"""

    prompt: str
    cwd: str | None = None
    model_id: str | None = None
    session_id: str | None = None
    reasoning: str | None = Field(
        default=None,
        description="推理强度 / OpenCode variant（可选）",
    )
    executable: str | None = Field(
        default=None,
        description="Tauri 扫描到的 CLI 绝对路径（优先于 PATH 再解析）",
    )
    extra_allowed_dirs: list[str] | None = None
    run_id: str | None = None
    platform_hint: str | None = Field(
        default=None,
        description="本轮优先平台：xianyu / xiaohongshu / ali1688",
    )
    context_messages: list[dict[str, Any]] | None = Field(
        default=None,
        description="换 Agent 冷启动时由叮答托管的先前对话 [{role, content}, ...]",
    )


class AgentLiveFrameRequest(BaseModel):
    """MCP preview 投递的一帧截图。"""

    url: str = ""
    title: str = ""
    hint: str | None = None
    mime: str = "image/jpeg"
    image_b64: str


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


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


@router.post("/works/{work_id}/run")
async def run_agent_work(work_id: str, body: AgentWorkRunRequest) -> StreamingResponse:
    """产品 Agent SSE：进程内 Tool + Headroom + LLM。"""
    key = work_id.strip()
    if not key:
        raise AppError("agent.work_invalid_id", "work_id 不能为空", status_code=400)
    run_id = (body.run_id or f"run-{uuid.uuid4().hex[:12]}").strip()
    prompt = body.prompt.strip()
    logger.info("agent work run start work=%s run=%s", key, run_id)

    async def gen() -> AsyncIterator[str]:
        service = AgentService()
        async for event in service.run(prompt, run_id=run_id, runtime_id="dingda"):
            yield _sse(str(event.get("type") or "message"), {"runId": run_id, **event})

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/runtimes/{runtime_id}/run")
async def run_agent_runtime(
    runtime_id: str,
    body: AgentRuntimeRunRequest,
) -> StreamingResponse:
    """外部 CLI Runtime SSE（Python spawn）。"""
    rid = runtime_id.strip()
    run_id = (body.run_id or f"run-{uuid.uuid4().hex[:12]}").strip()
    prompt = body.prompt.strip()
    if not prompt:
        raise AppError("agent.prompt_required", "prompt 不能为空", status_code=400)
    logger.debug("agent runtime run start runtime=%s run=%s", rid, run_id)

    async def gen() -> AsyncIterator[str]:
        try:
            async for event in run_cli(
                rid,
                prompt,
                run_id=run_id,
                cwd=body.cwd,
                model_id=body.model_id,
                session_id=body.session_id,
                reasoning=body.reasoning,
                executable=body.executable,
                extra_allowed_dirs=body.extra_allowed_dirs,
                platform_hint=body.platform_hint,
                context_messages=body.context_messages,
            ):
                yield _sse(str(event.get("type") or "message"), {"runId": run_id, **event})
        except AppError as exc:
            yield _sse("error", {"runId": run_id, "type": "error", "message": exc.message})
            yield _sse(
                "runCompleted",
                {"runId": run_id, "type": "runCompleted", "exitCode": 1},
            )

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/runtimes/runs/{run_id}/live-frame")
async def post_agent_runtime_live_frame(
    run_id: str,
    body: AgentLiveFrameRequest,
) -> dict[str, Any]:
    """接收 MCP preview 推送的直播帧，供 SSE 侧 drain。"""
    key = run_id.strip()
    if not key:
        raise AppError("agent.run_invalid_id", "run_id 不能为空", status_code=400)
    if not body.image_b64.strip():
        raise AppError("agent.frame_empty", "image_b64 不能为空", status_code=400)
    mime = (body.mime or "image/jpeg").strip() or "image/jpeg"
    screenshot_url = f"data:{mime};base64,{body.image_b64.strip()}"
    page = page_from_live_frame(
        url=body.url or "",
        title=body.title or "",
        hint=body.hint,
        screenshot_url=screenshot_url,
    )
    live_hub.push_frame(
        key,
        {
            "type": "browserFrame",
            "url": page["url"],
            "title": page["title"],
            "hint": page.get("focus_label"),
            "screenshot_url": screenshot_url,
            "page": page,
        },
    )
    return {"ok": True, "run_id": key}


@router.post("/runtimes/runs/{run_id}/cancel")
async def cancel_agent_runtime_run(run_id: str) -> dict[str, Any]:
    """取消 Python 侧正在跑的 CLI。"""
    key = run_id.strip()
    if not key:
        raise AppError("agent.run_invalid_id", "run_id 不能为空", status_code=400)
    await cancel_run(key)
    return {"ok": True, "run_id": key}
