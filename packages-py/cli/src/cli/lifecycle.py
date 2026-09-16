"""Agent 运行阶段与快照。

职责：
    定义一次 AgentRun 的 ``AgentPhase`` 状态机与 ``AgentRunSnapshot``。
    供 ``AgentRunStore`` / ``SubAgentSession`` / SSE ``agentPhase`` 共用。

设计说明：
    - 合法迁移见 ``ALLOWED_TRANSITIONS``；非法迁移由 Store 拒绝
    - parent / worker / child 各一条快照，用 ``parent_run_id`` 串树

使用示例：
    snap = AgentRunSnapshot(run_id="r1", role="worker", phase=AgentPhase.PENDING, ...)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class AgentPhase(StrEnum):
    """一次 AgentRun 所处阶段。"""

    PENDING = "pending"
    RUNNING = "running"
    NEEDS_REPAIR = "needs_repair"
    REPAIRING = "repairing"
    RESUMING = "resuming"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# 合法边：from → frozenset[to]
ALLOWED_TRANSITIONS: dict[AgentPhase, frozenset[AgentPhase]] = {
    AgentPhase.PENDING: frozenset({AgentPhase.RUNNING, AgentPhase.RESUMING, AgentPhase.CANCELLED}),
    AgentPhase.RUNNING: frozenset(
        {
            AgentPhase.NEEDS_REPAIR,
            AgentPhase.COMPLETED,
            AgentPhase.FAILED,
            AgentPhase.CANCELLED,
        }
    ),
    AgentPhase.NEEDS_REPAIR: frozenset(
        {
            AgentPhase.REPAIRING,
            AgentPhase.RESUMING,
            AgentPhase.FAILED,
            AgentPhase.CANCELLED,
        }
    ),
    AgentPhase.REPAIRING: frozenset(
        {AgentPhase.RESUMING, AgentPhase.FAILED, AgentPhase.CANCELLED}
    ),
    AgentPhase.RESUMING: frozenset(
        {AgentPhase.RUNNING, AgentPhase.FAILED, AgentPhase.CANCELLED}
    ),
    AgentPhase.COMPLETED: frozenset(),
    AgentPhase.FAILED: frozenset(),
    AgentPhase.CANCELLED: frozenset(),
}


@dataclass
class AgentRunSnapshot:
    """一次 Agent 运行的可查询快照（程序侧真相源）。"""

    run_id: str
    role: str
    phase: AgentPhase
    parent_run_id: str | None = None
    session_id: str | None = None
    runtime_id: str = ""
    model_id: str | None = None
    task: str = ""
    step: str | None = None
    error_code: str | None = None
    repair: dict[str, Any] | None = None
    updated_at: float = 0.0
    # 子 run 列表缓存键以外的扩展字段不放这里

    def to_phase_event(self) -> dict[str, Any]:
        """收成 SSE ``agentPhase`` 事件载荷。"""
        return {
            "type": "agentPhase",
            "runId": self.run_id,
            "role": self.role,
            "phase": str(self.phase),
            "parentRunId": self.parent_run_id,
            "sessionId": self.session_id,
            "step": self.step,
            "errorCode": self.error_code,
        }


def can_transition(current: AgentPhase, target: AgentPhase) -> bool:
    """当前阶段是否允许迁到目标。"""
    if current == target:
        return True
    return target in ALLOWED_TRANSITIONS.get(current, frozenset())
