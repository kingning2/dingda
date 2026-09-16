"""编排工具 child_status / child_run 接线单测（不启真实 CLI）。"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from cli.subagent import SubAgentResult
from cli.lifecycle import AgentPhase, AgentRunSnapshot
from cli.registry import reset_orchestrate_singletons
from cli.runs import MemoryAgentRunStore
from tools.child_run import ChildRunInput, run_child_run
from tools.child_status import ChildStatusInput, run_child_status


def test_child_status_reads_store(monkeypatch) -> None:
    reset_orchestrate_singletons()
    store = MemoryAgentRunStore()
    store.upsert(
        AgentRunSnapshot(
            run_id="child-1",
            role="worker",
            phase=AgentPhase.NEEDS_REPAIR,
            session_id="ses",
            error_code="crawler.needs_repair",
            repair={"platform": "xianyu", "item_id": "1"},
            task="搜",
            step="needs_repair",
        )
    )
    monkeypatch.setattr("cli.registry.get_run_store", lambda: store)
    monkeypatch.setattr("cli.registry.get_run_store", lambda: store)

    out = asyncio.run(run_child_status(ChildStatusInput(run_id="child-1")))
    assert out.found is True
    assert out.phase == "needs_repair"
    assert out.error_code == "crawler.needs_repair"
    assert out.repair == {"platform": "xianyu", "item_id": "1"}


def test_child_run_delegates_to_session(monkeypatch) -> None:
    reset_orchestrate_singletons()
    fake = AsyncMock(
        return_value=SubAgentResult(
            ok=True,
            run_id="r9",
            session_id="s9",
            exit_code=0,
            phase="completed",
            summary="done",
        )
    )

    class _Sess:
        run = fake

    monkeypatch.setattr("cli.registry.get_subagent_session", lambda: _Sess())
    out = asyncio.run(run_child_run(ChildRunInput(task="搜露营椅")))
    assert out.ok is True
    assert out.run_id == "r9"
    assert out.phase == "completed"
    fake.assert_awaited_once()
