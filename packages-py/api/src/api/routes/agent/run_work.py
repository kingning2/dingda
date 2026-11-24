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

from domains.agent.service import AgentService
from api.routes.agent._dto import AgentWorkRunRequest
from api.routes.sse import sse_frame
from core.errors import AppError
from core.logging import bind_trace, reset_trace

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

    async def gen() -> AsyncIterator[str]:
        # trace 绑定在流生成器里（真正执行 run 的上下文）：SSE 帧里的 runId
        # 与服务端日志 trace=<id> 同源，前端报 bug 时报 runId 即可对上日志
        token = bind_trace(run_id)
        try:
            logger.info("agent work run start work=%s", key)
            service = AgentService()
            async for event in service.run(prompt, run_id=run_id, runtime_id="dingda"):
                yield sse_frame(str(event.get("type") or "message"), {"runId": run_id, **event})
        finally:
            reset_trace(token)

    return StreamingResponse(gen(), media_type="text/event-stream")
