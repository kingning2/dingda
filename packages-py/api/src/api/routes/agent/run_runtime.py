"""外部 CLI Runtime 运行端点。

职责：
    外部 CLI Runtime SSE（Python spawn）：把 CLI 子进程事件流转发给前端。
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from api.routes.agent._dto import AgentRuntimeRunRequest
from api.routes.sse import sse_frame
from cli.spawn import run_cli
from core.errors import AppError

logger = logging.getLogger("dingda.api.agent")

router = APIRouter()


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
                yield sse_frame(str(event.get("type") or "message"), {"runId": run_id, **event})
        except AppError as exc:
            yield sse_frame("error", {"runId": run_id, "type": "error", "message": exc.message})
            yield sse_frame(
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
