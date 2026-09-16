"""编排 Tool：child_run（拉起 worker 子会话）。

职责：
    父编排器派工入口；调 ``cli.registry.get_subagent_session().run``。

使用示例：
    out = await run_child_run(ChildRunInput(task="搜闲鱼露营椅"))
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger("dingda.tools.child_run")

TOOL_NAME = "child_run"
TOOL_DESCRIPTION = (
    "拉起 worker 子会话执行选品/比价任务。"
    "返回 run_id / session_id / phase；若 phase=needs_repair 先 repair_dom 再 child_resume。"
)
DEFAULT_TIMEOUT_S = 3600.0


class ChildRunInput(BaseModel):
    """派工入参。"""

    task: str = Field(description="给 worker 的任务说明")
    role: str = Field(default="worker", description="子会话角色，默认 worker")
    runtime_id: str | None = Field(default=None, description="覆盖 CLI runtime；默认继承父环境")
    model_id: str | None = Field(default=None, description="覆盖模型；默认继承父环境")


class ChildRunOutput(BaseModel):
    """派工出参。"""

    ok: bool = True
    run_id: str = ""
    session_id: str | None = None
    exit_code: int = 0
    phase: str = ""
    error_code: str | None = None
    summary: str = ""
    repair: dict[str, Any] | None = None


async def run_child_run(inp: ChildRunInput) -> ChildRunOutput:
    """起子会话并阻塞到结束。"""
    from cli.registry import get_subagent_session

    logger.info("tool start name=child_run role=%s", inp.role)
    result = await get_subagent_session().run(
        inp.task,
        role=(inp.role or "worker").strip() or "worker",
        runtime_id=inp.runtime_id,
        model_id=inp.model_id,
    )
    logger.info(
        "tool done name=child_run run=%s phase=%s",
        result.run_id,
        result.phase,
    )
    return ChildRunOutput(
        ok=result.ok,
        run_id=result.run_id,
        session_id=result.session_id,
        exit_code=result.exit_code,
        phase=result.phase,
        error_code=result.error_code,
        summary=result.summary,
        repair=result.repair,
    )
