"""子 agent 会话插座 + CLI 插头。

职责：
    定义父编排器起 / 续 / 停子 CLI 的统一接口（``SubAgentSession`` 插座 + ``SubAgentResult``），
    以及外部 CLI 插头 ``CliSubAgentSession``：用 ``run_cli`` / ``cancel_run`` 起停子 Agent，
    写入 ``AgentRunStore``，向父 run 的 live hub 推 ``agentPhase`` 事件。

设计说明：
    - 不是第二套编排 LLM：只管理子进程生命周期与阶段写入
    - runtime / model 默认继承环境变量 ``DINGDA_AGENT_RUNTIME`` / ``DINGDA_LLM_MODEL``
    - 从 toolResult / 文本里识别 ``crawler.needs_repair`` 并迁到 needs_repair
    - 子 live 帧（browserFrame）转发到父 run_id，UI 仍挂在父 SSE
    - ``_execute`` 拆成「开快照 → 消费事件 → 收尾定相」三步，便于读

使用示例：
    session = get_subagent_session()  # 见 registry
    result = await session.run("搜闲鱼露营椅", role="worker", parent_run_id="p1")
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from cli import live as live_hub
from cli.lifecycle import AgentPhase, AgentRunSnapshot
from cli.runs import AgentRunStore
from cli.spawn import cancel_run, run_cli

logger = logging.getLogger("dingda.cli.subagent")

_NEEDS_REPAIR = "crawler.needs_repair"
# 终态集合：cancel 见到这些就不强制改写
_CLOSED_PHASES = frozenset(
    {AgentPhase.COMPLETED, AgentPhase.FAILED, AgentPhase.CANCELLED}
)


@dataclass(frozen=True)
class SubAgentResult:
    """子会话一次跑完的结果。"""

    ok: bool
    run_id: str
    session_id: str | None
    exit_code: int
    phase: str
    error_code: str | None = None
    summary: str = ""
    repair: dict[str, Any] | None = None


class SubAgentSession(ABC):
    """子 agent 会话插座：起 / 续 / 停。"""

    @abstractmethod
    async def run(
        self,
        task: str,
        *,
        role: str = "worker",
        runtime_id: str | None = None,
        model_id: str | None = None,
        parent_run_id: str | None = None,
    ) -> SubAgentResult:
        """新开子会话跑任务。"""

    @abstractmethod
    async def resume(
        self,
        session_id: str,
        message: str,
        *,
        role: str = "worker",
        runtime_id: str | None = None,
        model_id: str | None = None,
        parent_run_id: str | None = None,
        run_id: str | None = None,
    ) -> SubAgentResult:
        """按 CLI session 续聊。"""

    @abstractmethod
    async def cancel(self, run_id: str) -> None:
        """杀掉正在跑的子会话。"""


@dataclass
class _Outcome:
    """一轮 ``run_cli`` 的中间结果，供收尾定相。"""

    exit_code: int = 1
    cli_session: str | None = None
    error_code: str | None = None
    repair: dict[str, Any] | None = None
    summary_parts: list[str] = field(default_factory=list)


class CliSubAgentSession(SubAgentSession):
    """外部 CLI 子会话插头。"""

    def __init__(self, *, store: AgentRunStore) -> None:
        self._store = store

    async def run(
        self,
        task: str,
        *,
        role: str = "worker",
        runtime_id: str | None = None,
        model_id: str | None = None,
        parent_run_id: str | None = None,
    ) -> SubAgentResult:
        """新开子 CLI 跑任务。"""
        return await self._execute(
            task,
            session_id=None,
            role=role,
            runtime_id=runtime_id,
            model_id=model_id,
            parent_run_id=parent_run_id,
            run_id=None,
            resuming=False,
        )

    async def resume(
        self,
        session_id: str,
        message: str,
        *,
        role: str = "worker",
        runtime_id: str | None = None,
        model_id: str | None = None,
        parent_run_id: str | None = None,
        run_id: str | None = None,
    ) -> SubAgentResult:
        """续聊已有 CLI session。"""
        sid = (session_id or "").strip()
        if not sid:
            return SubAgentResult(
                ok=False,
                run_id="",
                session_id=None,
                exit_code=1,
                phase=AgentPhase.FAILED,
                error_code="cli.session_required",
                summary="resume 需要 session_id",
            )
        existing = self._store.find_by_session(sid)
        parent = parent_run_id or (existing.parent_run_id if existing else None)
        return await self._execute(
            message,
            session_id=sid,
            role=role,
            runtime_id=runtime_id,
            model_id=model_id,
            parent_run_id=parent,
            run_id=run_id or (existing.run_id if existing else None),
            resuming=True,
        )

    async def cancel(self, run_id: str) -> None:
        """杀掉子 CLI 并标 cancelled。"""
        rid = (run_id or "").strip()
        if not rid:
            return
        logger.info("subagent cancel run=%s", rid)
        await cancel_run(rid)
        snap = self._store.get(rid)
        if snap and snap.phase not in _CLOSED_PHASES:
            self._transition_and_push(
                rid,
                AgentPhase.CANCELLED,
                step="cancel",
                parent_run_id=snap.parent_run_id,
            )

    async def _execute(
        self,
        prompt: str,
        *,
        session_id: str | None,
        role: str,
        runtime_id: str | None,
        model_id: str | None,
        parent_run_id: str | None,
        run_id: str | None,
        resuming: bool,
    ) -> SubAgentResult:
        """跑一遍 run_cli，维护 Store 与父 SSE。"""
        rid, runtime, model, parent = self._open_run(
            prompt,
            session_id,
            role,
            runtime_id,
            model_id,
            parent_run_id,
            run_id,
            resuming,
        )
        outcome = await self._consume_events(
            rid, prompt, session_id, role, runtime, model, parent
        )
        return self._finish(rid, parent, outcome)

    def _open_run(
        self,
        prompt: str,
        session_id: str | None,
        role: str,
        runtime_id: str | None,
        model_id: str | None,
        parent_run_id: str | None,
        run_id: str | None,
        resuming: bool,
    ) -> tuple[str, str, str | None, str | None]:
        """建 / 续快照并迁到 RUNNING。"""
        rid = (run_id or f"child-{uuid.uuid4().hex[:12]}").strip()
        runtime = (runtime_id or os.getenv("DINGDA_AGENT_RUNTIME") or "codex").strip()
        model = (model_id or os.getenv("DINGDA_LLM_MODEL") or "").strip() or None
        parent = (parent_run_id or os.getenv("DINGDA_AGENT_RUN_ID") or "").strip() or None

        live_hub.open_run(rid)
        existing = self._store.get(rid)
        if existing is None:
            snap = AgentRunSnapshot(
                run_id=rid,
                role=role,
                phase=AgentPhase.PENDING,
                parent_run_id=parent,
                session_id=session_id,
                runtime_id=runtime,
                model_id=model,
                task=(prompt or "")[:500],
                step="resume" if resuming else "spawn",
            )
            self._store.upsert(snap)
            self._push_phase(snap, parent)
        else:
            existing.task = (prompt or "")[:500]
            existing.parent_run_id = parent or existing.parent_run_id
            existing.session_id = session_id or existing.session_id
            existing.runtime_id = runtime
            existing.model_id = model
            self._store.upsert(existing)

        if resuming:
            cur = self._store.get(rid)
            if cur and cur.phase in {
                AgentPhase.NEEDS_REPAIR,
                AgentPhase.REPAIRING,
                AgentPhase.PENDING,
            }:
                if cur.phase != AgentPhase.RESUMING:
                    self._transition_and_push(
                        rid, AgentPhase.RESUMING, step="resume", parent_run_id=parent
                    )
        self._transition_and_push(
            rid, AgentPhase.RUNNING, step="running", parent_run_id=parent
        )

        logger.info(
            "subagent start run=%s role=%s runtime=%s resume=%s parent=%s",
            rid,
            role,
            runtime,
            bool(session_id),
            parent or "-",
        )
        return rid, runtime, model, parent

    async def _consume_events(
        self,
        rid: str,
        prompt: str,
        session_id: str | None,
        role: str,
        runtime: str,
        model: str | None,
        parent: str | None,
    ) -> _Outcome:
        """跑 ``run_cli``，把事件收成 ``_Outcome``。"""
        outcome = _Outcome()
        try:
            async for event in run_cli(
                runtime,
                prompt,
                run_id=rid,
                model_id=model,
                session_id=session_id,
                role=role,
            ):
                kind = str(event.get("type") or "")
                if kind == "session":
                    sid = str(event.get("sessionId") or "").strip()
                    if sid:
                        outcome.cli_session = sid
                        self._store.transition(rid, AgentPhase.RUNNING, session_id=sid)
                elif kind == "toolCall":
                    name = str(event.get("name") or "tool")
                    self._transition_and_push(
                        rid,
                        AgentPhase.RUNNING,
                        step=f"tool={name}",
                        parent_run_id=parent,
                    )
                elif kind == "toolResult":
                    parsed = _parse_tool_output(event.get("output"))
                    if parsed.get("error_code") == _NEEDS_REPAIR:
                        outcome.error_code = _NEEDS_REPAIR
                        outcome.repair = _repair_payload(parsed)
                        self._transition_and_push(
                            rid,
                            AgentPhase.NEEDS_REPAIR,
                            step="needs_repair",
                            error_code=outcome.error_code,
                            repair=outcome.repair,
                            parent_run_id=parent,
                        )
                elif kind == "textDelta":
                    text = str(event.get("text") or "")
                    if text.strip():
                        outcome.summary_parts.append(text)
                    if _NEEDS_REPAIR in text and outcome.error_code is None:
                        outcome.error_code = _NEEDS_REPAIR
                elif kind == "browserFrame" and parent:
                    live_hub.push_frame(parent, event)
                elif kind == "runCompleted":
                    outcome.exit_code = int(event.get("exitCode") or 0)
                elif kind == "error":
                    outcome.summary_parts.append(str(event.get("message") or "error"))
        except Exception as exc:  # noqa: BLE001
            logger.exception("subagent failed run=%s", rid)
            outcome.error_code = outcome.error_code or "cli.subagent_failed"
            self._transition_and_push(
                rid,
                AgentPhase.FAILED,
                step="exception",
                error_code=outcome.error_code,
                parent_run_id=parent,
            )
            outcome.summary_parts.append(str(exc)[:500])
        return outcome

    def _finish(self, rid: str, parent: str | None, outcome: _Outcome) -> SubAgentResult:
        """按 run_cli 结果定 phase 并收尾。"""
        current = self._store.get(rid)
        if current and current.phase == AgentPhase.NEEDS_REPAIR:
            phase = AgentPhase.NEEDS_REPAIR
            outcome.error_code = outcome.error_code or _NEEDS_REPAIR
            outcome.repair = outcome.repair or current.repair
        elif outcome.exit_code == 0 and outcome.error_code != _NEEDS_REPAIR:
            phase = AgentPhase.COMPLETED
            self._transition_and_push(rid, phase, step="done", parent_run_id=parent)
        else:
            phase = (
                AgentPhase.FAILED
                if outcome.error_code != _NEEDS_REPAIR
                else AgentPhase.NEEDS_REPAIR
            )
            if current and current.phase == AgentPhase.RUNNING:
                self._transition_and_push(
                    rid,
                    phase,
                    step="done",
                    error_code=outcome.error_code,
                    repair=outcome.repair,
                    parent_run_id=parent,
                )

        summary = "".join(outcome.summary_parts).strip()[-800:]
        ok = phase == AgentPhase.COMPLETED
        logger.info(
            "subagent done run=%s phase=%s exit=%s error=%s",
            rid,
            phase,
            outcome.exit_code,
            outcome.error_code or "-",
        )
        return SubAgentResult(
            ok=ok,
            run_id=rid,
            session_id=outcome.cli_session,
            exit_code=outcome.exit_code,
            phase=str(phase),
            error_code=outcome.error_code,
            summary=summary,
            repair=outcome.repair,
        )

    def _transition_and_push(
        self,
        run_id: str,
        phase: AgentPhase,
        *,
        parent_run_id: str | None,
        step: str | None = None,
        **fields: Any,
    ) -> None:
        """迁阶段并推父 SSE。"""
        try:
            snap = self._store.transition(run_id, phase, step=step, **fields)
        except KeyError:
            return
        self._push_phase(snap, parent_run_id or snap.parent_run_id)

    def _push_phase(self, snap: AgentRunSnapshot, parent_run_id: str | None) -> None:
        """把 agentPhase 推到父 run（若有）；同时推本 run。"""
        event = snap.to_phase_event()
        live_hub.push_frame(snap.run_id, event)
        parent = (parent_run_id or "").strip()
        if parent and parent != snap.run_id:
            live_hub.push_frame(parent, event)


def _parse_tool_output(raw: Any) -> dict[str, Any]:
    """toolResult.output → dict。"""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _repair_payload(parsed: dict[str, Any]) -> dict[str, Any] | None:
    """从工具出参抠 repair 字段。"""
    repair = parsed.get("repair")
    if isinstance(repair, dict):
        return repair
    out: dict[str, Any] = {}
    for key in ("platform", "item_id", "url"):
        value = parsed.get(key)
        if value:
            out[key] = value
    return out or None
