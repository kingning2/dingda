"""编排 Tool：child_cancel（杀掉子会话）。

职责：
    父编排器发现越界或用户中止时终止子 CLI。
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

logger = logging.getLogger("dingda.tools.child_cancel")

TOOL_NAME = "child_cancel"
TOOL_DESCRIPTION = "终止正在跑的子会话（越界或用户中止）。"
DEFAULT_TIMEOUT_S = 30.0


class ChildCancelInput(BaseModel):
    """取消入参。"""

    run_id: str = Field(description="子会话 run_id")


class ChildCancelOutput(BaseModel):
    """取消出参。"""

    ok: bool = True
    run_id: str = ""
    message: str | None = None


async def run_child_cancel(inp: ChildCancelInput) -> ChildCancelOutput:
    """取消子会话。"""
    from cli.registry import get_subagent_session

    rid = (inp.run_id or "").strip()
    logger.info("tool start name=child_cancel run=%s", rid)
    await get_subagent_session().cancel(rid)
    logger.info("tool done name=child_cancel run=%s", rid)
    return ChildCancelOutput(ok=True, run_id=rid, message="cancelled")
