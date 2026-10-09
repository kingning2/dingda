"""直播帧接收端点。

职责：
    接收 MCP preview 推送的直播截图帧，供 SSE 侧 drain 到前端。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from api.routes.agent._dto import AgentLiveFrameRequest
from cli.live import hub as live_hub
from cli.steps import page_from_live_frame
from core.errors import AppError

router = APIRouter()


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
