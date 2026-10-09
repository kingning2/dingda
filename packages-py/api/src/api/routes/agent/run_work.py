"""产品 Agent 运行端点。

职责：
    产品 Agent SSE：进程内 Tool + Headroom + LLM，事件逐帧推给前端。
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from agent.core.agent import AgentService
from api.routes.agent._dto import AgentWorkRunRequest
from api.routes.sse import sse_frame
from core.errors import AppError

logger = logging.getLogger("dingda.api.agent")

router = APIRouter()


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
            yield sse_frame(str(event.get("type") or "message"), {"runId": run_id, **event})

    return StreamingResponse(gen(), media_type="text/event-stream")
