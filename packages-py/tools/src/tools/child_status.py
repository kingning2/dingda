"""编排 Tool：child_status（查子会话阶段）。

职责：
    读 ``AgentRunStore``，告诉父编排器子会话走到哪。
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger("dingda.tools.child_status")

TOOL_NAME = "child_status"
TOOL_DESCRIPTION = "查询子会话当前 phase / step / error_code（按 run_id 或 session_id）。"
DEFAULT_TIMEOUT_S = 10.0


class ChildStatusInput(BaseModel):
    """查询入参。"""

    run_id: str | None = Field(default=None, description="子 run_id")
    session_id: str | None = Field(default=None, description="CLI session id")

    @model_validator(mode="after")
    def _need_one(self) -> ChildStatusInput:
        if not (self.run_id or "").strip() and not (self.session_id or "").strip():
            raise ValueError("需要 run_id 或 session_id")
        return self


class ChildStatusOutput(BaseModel):
    """查询出参。"""

    ok: bool = True
    found: bool = False
    run_id: str | None = None
    role: str | None = None
    phase: str | None = None
    step: str | None = None
    session_id: str | None = None
    parent_run_id: str | None = None
    error_code: str | None = None
    repair: dict[str, Any] | None = None
    task: str | None = None
    message: str | None = None


async def run_child_status(inp: ChildStatusInput) -> ChildStatusOutput:
    """查 Store 快照。"""
    from cli.registry import get_run_store

    store = get_run_store()
    snap = None
    if (inp.run_id or "").strip():
        snap = store.get(inp.run_id.strip())
    elif (inp.session_id or "").strip():
        snap = store.find_by_session(inp.session_id.strip())
    if snap is None:
        logger.info("tool child_status miss")
        return ChildStatusOutput(ok=True, found=False, message="not found")
    logger.info(
        "tool child_status hit run=%s phase=%s",
        snap.run_id,
        snap.phase,
    )
    return ChildStatusOutput(
        ok=True,
        found=True,
        run_id=snap.run_id,
        role=snap.role,
        phase=str(snap.phase),
        step=snap.step,
        session_id=snap.session_id,
        parent_run_id=snap.parent_run_id,
        error_code=snap.error_code,
        repair=snap.repair,
        task=snap.task,
    )
