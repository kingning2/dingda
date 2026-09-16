"""编排 Tool：child_resume（续聊 worker）。

职责：
    DOM 修复后或用户增量后，按 session_id 续聊子会话。
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger("dingda.tools.child_resume")

TOOL_NAME = "child_resume"
TOOL_DESCRIPTION = (
    "按 session_id 续聊 worker。"
    "repair_dom 成功后应立刻调用，message 说明「已修复请继续」。"
)
DEFAULT_TIMEOUT_S = 3600.0


class ChildResumeInput(BaseModel):
    """续聊入参。"""

    session_id: str = Field(description="worker 的 CLI session id")
    message: str = Field(description="续聊增量")
    role: str = Field(default="worker", description="子会话角色")
    run_id: str | None = Field(default=None, description="已有子 run_id；可空")
    runtime_id: str | None = Field(default=None, description="覆盖 runtime")
    model_id: str | None = Field(default=None, description="覆盖模型")


class ChildResumeOutput(BaseModel):
    """续聊出参。"""

    ok: bool = True
    run_id: str = ""
    session_id: str | None = None
    exit_code: int = 0
    phase: str = ""
    error_code: str | None = None
    summary: str = ""
    repair: dict[str, Any] | None = None


async def run_child_resume(inp: ChildResumeInput) -> ChildResumeOutput:
    """续聊子会话。"""
    from cli.registry import get_subagent_session

    logger.info("tool start name=child_resume session=%s", inp.session_id)
    result = await get_subagent_session().resume(
        inp.session_id,
        inp.message,
        role=(inp.role or "worker").strip() or "worker",
        runtime_id=inp.runtime_id,
        model_id=inp.model_id,
        run_id=inp.run_id,
    )
    logger.info(
        "tool done name=child_resume run=%s phase=%s",
        result.run_id,
        result.phase,
    )
    return ChildResumeOutput(
        ok=result.ok,
        run_id=result.run_id,
        session_id=result.session_id,
        exit_code=result.exit_code,
        phase=result.phase,
        error_code=result.error_code,
        summary=result.summary,
        repair=result.repair,
    )
