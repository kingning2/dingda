"""Agent 生命周期 Store / phase 迁移单测。"""

from __future__ import annotations

from cli.lifecycle import AgentPhase, AgentRunSnapshot, can_transition
from cli.runs import MemoryAgentRunStore


def test_allowed_transitions() -> None:
    assert can_transition(AgentPhase.PENDING, AgentPhase.RUNNING)
    assert can_transition(AgentPhase.RUNNING, AgentPhase.NEEDS_REPAIR)
    assert can_transition(AgentPhase.NEEDS_REPAIR, AgentPhase.REPAIRING)
    assert can_transition(AgentPhase.REPAIRING, AgentPhase.RESUMING)
    assert can_transition(AgentPhase.RESUMING, AgentPhase.RUNNING)
    assert not can_transition(AgentPhase.COMPLETED, AgentPhase.RUNNING)
    assert not can_transition(AgentPhase.FAILED, AgentPhase.RUNNING)


def test_memory_store_transition_and_reject() -> None:
    store = MemoryAgentRunStore()
    store.upsert(
        AgentRunSnapshot(
            run_id="r1",
            role="worker",
            phase=AgentPhase.PENDING,
            parent_run_id="p1",
            task="搜",
        )
    )
    snap = store.transition("r1", AgentPhase.RUNNING, step="tool=search")
    assert snap.phase == AgentPhase.RUNNING
    assert snap.step == "tool=search"

    rejected = store.transition("r1", AgentPhase.RESUMING)
    assert rejected.phase == AgentPhase.RUNNING

    store.transition("r1", AgentPhase.NEEDS_REPAIR, error_code="crawler.needs_repair")
    kids = store.list_children("p1")
    assert len(kids) == 1
    assert kids[0].error_code == "crawler.needs_repair"


def test_find_by_session() -> None:
    store = MemoryAgentRunStore()
    store.upsert(
        AgentRunSnapshot(
            run_id="a",
            role="worker",
            phase=AgentPhase.RUNNING,
            session_id="ses_1",
        )
    )
    store.upsert(
        AgentRunSnapshot(
            run_id="b",
            role="worker",
            phase=AgentPhase.NEEDS_REPAIR,
            session_id="ses_1",
        )
    )
    found = store.find_by_session("ses_1")
    assert found is not None
    assert found.run_id == "b"
