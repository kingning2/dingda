"""Agent HTTP 路由。

职责：
    AI 工作对话快照读写，以及 Agent 运行入口（SSE）。

设计说明：
    - 对话快照落在 ``agent_works``
    - **运行入口的接线在 [agent_run.py](agent_run.py)**：本文件只管校验入参、把
      ``stream_run`` / ``resume_run`` 包成 ``StreamingResponse``。编排在
      ``agent.run.run_chat`` → ``agent.orchestrator.run_orchestrator``；
      生命周期与投递日志在 ``agent.runs``。请求模型也定义在 ``agent_run`` 里 ——
      放在本文件会让 ``agent_run`` 反过来 import 本模块，绕成环
    - **两条起手路径共用一条实现**：``runtime_id`` 已无实际含义（外部 CLI 对接删掉后
      只剩一种实现），保留路径是为了不动前端既有调用
    - **run 活得比请求长**：断开只退订，接回走 ``GET /runtimes/runs/{run_id}/events``，
      进页面的活跃探针走 ``GET /works/{work_id}/active-run``
    - SSE 收尾事件由 ``agent.runs`` 保证发出：前端靠 ``runCompleted`` 把界面从
      「运行中」放下来，漏发会让消息永远转圈
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from contracts.agent import (
    AgentActiveRunView,
    AgentWorkDetailResponse,
    AgentWorkListResponse,
    AgentWorkPutRequest,
    AgentWorkSummaryView,
)
from core.errors import AppError
from infrastructure.db import agent_works as works_repo

from api.agent_run import AgentRunRequest, cancel_run, manager, resume_run, stream_run

logger = logging.getLogger("dingda.api.agent")

router = APIRouter(prefix="/v1/agent", tags=["agent"])

_SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


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


def _sse_response(body: AgentRunRequest, *, runtime_id: str) -> StreamingResponse:
    """把一次运行包成 SSE 响应。

    ``prompt`` 为空在这里挡掉：真跑到发动机才报错的话，前端得先建好一条空消息、
    再看到它变红，不如请求直接失败。
    """
    run_id = (body.run_id or f"run-{uuid.uuid4().hex[:12]}").strip()
    prompt = body.prompt.strip()
    if not prompt:
        raise AppError("agent.prompt_required", "prompt 不能为空", status_code=400)
    logger.info("agent run start run=%s runtime=%s prompt_len=%s", run_id, runtime_id, len(prompt))

    return StreamingResponse(
        stream_run(run_id=run_id, runtime_id=runtime_id, request=body),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.post("/works/{work_id}/run")
async def run_agent_work(work_id: str, body: AgentRunRequest) -> StreamingResponse:
    """在某个工作对话里跑一轮 Agent。"""
    key = work_id.strip()
    if not key:
        raise AppError("agent.work_invalid_id", "work_id 不能为空", status_code=400)
    return _sse_response(body, runtime_id=key)


@router.post("/runtimes/{runtime_id}/run")
async def run_agent_runtime(runtime_id: str, body: AgentRunRequest) -> StreamingResponse:
    """运行入口（前端走的就是这条）。

    ``runtime_id`` 只进日志与 ``runStarted`` 事件，不参与选路。
    """
    return _sse_response(body, runtime_id=runtime_id.strip())


@router.post("/runtimes/runs/{run_id}/cancel")
async def cancel_agent_runtime_run(run_id: str) -> dict[str, object]:
    """取消一次运行。

    只能停在步与步之间：正在跑的浏览器抓取不会被打断（那要能中断 Playwright 的调用链）。
    没有对应的在跑运行也回 ``ok``：前端 abort fetch 是另一条独立的取消路径，
    这里报错只会让用户在控制台看到一堆无意义的失败。
    """
    key = run_id.strip()
    if not key:
        raise AppError("agent.run_invalid_id", "run_id 不能为空", status_code=400)
    signalled = cancel_run(key)
    logger.info("agent run cancel run=%s signalled=%s", key, signalled)
    return {"ok": True, "run_id": key, "signalled": signalled}


@router.get("/runtimes/runs/{run_id}/events")
async def resume_agent_run(run_id: str, after: int = 0) -> StreamingResponse:
    """接回一次运行：先重放 ``seq > after`` 的已投递事件，再续上直播直到跑完。

    客户端断开只退订，run 仍在服务端跑（见 ``agent.runs``）—— 这条端点就是
    「关掉应用 / 刷新 / 断网之后接回来」的入口。查不到就 404：那说明 run 已经
    结束并被回收，客户端该按「上次执行已中断」收尾，而不是干等一个空流。
    """
    key = run_id.strip()
    if not key:
        raise AppError("agent.run_invalid_id", "run_id 不能为空", status_code=400)
    if manager.get(key) is None:
        raise AppError("agent.run_not_found", "这次运行已经结束", status_code=404)
    logger.info("agent run resume run=%s after=%s", key, after)

    return StreamingResponse(
        resume_run(run_id=key, after=after),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.get("/works/{work_id}/active-run", response_model=AgentActiveRunView)
async def get_active_agent_run(work_id: str) -> AgentActiveRunView:
    """这个工作对话下有没有在跑的 run。

    进页面时的活跃探针：有在跑的 run 就接回，没有才走「上次执行已中断」那条路。
    顺带回收过期 run —— 这条端点是唯一保证会被打开的入口。
    """
    key = work_id.strip()
    if not key:
        raise AppError("agent.work_invalid_id", "work_id 不能为空", status_code=400)
    manager.reap()
    record = manager.active_for_work(key)
    if record is None:
        return AgentActiveRunView(work_id=key)
    logger.info("agent active run probe work=%s run=%s seq=%s", key, record.run_id, record.seq)
    return AgentActiveRunView(
        work_id=key,
        run_id=record.run_id,
        seq=record.seq,
        status=record.status,
    )
