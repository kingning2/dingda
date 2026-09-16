"""Agent 运行快照存储插座。

职责：
    按 ``run_id`` 登记 / 查询 / 阶段迁移；列出某父 run 下的子 run。
    供编排工具 ``child_status`` 与 ``CliSubAgentSession`` 读写。

设计说明：
    - v1 插头 ``MemoryAgentRunStore``：进程内 dict，与 live hub 同寿命
    - 非法 phase 迁移打 warning 并拒绝（返回旧快照）

使用示例：
    store = MemoryAgentRunStore()
    store.upsert(snap)
    store.transition(run_id, AgentPhase.RUNNING, step="tool=search")
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

from cli.lifecycle import (
    AgentPhase,
    AgentRunSnapshot,
    can_transition,
)

logger = logging.getLogger("dingda.cli.runs")


class AgentRunStore(ABC):
    """Agent 运行快照插座。"""

    @abstractmethod
    def upsert(self, snap: AgentRunSnapshot) -> None:
        """写入或覆盖一条快照。"""

    @abstractmethod
    def get(self, run_id: str) -> AgentRunSnapshot | None:
        """按 run_id 取快照；没有则 None。"""

    @abstractmethod
    def find_by_session(self, session_id: str) -> AgentRunSnapshot | None:
        """按 CLI session_id 取最近一条快照。"""

    @abstractmethod
    def list_children(self, parent_run_id: str) -> list[AgentRunSnapshot]:
        """列出某父 run 下的子 run。"""

    @abstractmethod
    def transition(
        self,
        run_id: str,
        phase: AgentPhase,
        *,
        step: str | None = None,
        **fields: Any,
    ) -> AgentRunSnapshot:
        """合法迁移 phase；非法则打日志并返回旧快照。"""


class MemoryAgentRunStore(AgentRunStore):
    """进程内内存插头。"""

    def __init__(self) -> None:
        self._by_id: dict[str, AgentRunSnapshot] = {}

    def upsert(self, snap: AgentRunSnapshot) -> None:
        """写入快照并刷新 updated_at。"""
        snap.updated_at = time.time()
        self._by_id[snap.run_id] = snap
        logger.debug(
            "run store upsert id=%s role=%s phase=%s",
            snap.run_id,
            snap.role,
            snap.phase,
        )

    def get(self, run_id: str) -> AgentRunSnapshot | None:
        """按 id 取。"""
        key = (run_id or "").strip()
        return self._by_id.get(key) if key else None

    def find_by_session(self, session_id: str) -> AgentRunSnapshot | None:
        """按 session 取最新一条。"""
        sid = (session_id or "").strip()
        if not sid:
            return None
        matches = [s for s in self._by_id.values() if s.session_id == sid]
        if not matches:
            return None
        return max(matches, key=lambda s: s.updated_at)

    def list_children(self, parent_run_id: str) -> list[AgentRunSnapshot]:
        """按父 id 列子。"""
        pid = (parent_run_id or "").strip()
        rows = [s for s in self._by_id.values() if s.parent_run_id == pid]
        return sorted(rows, key=lambda s: s.updated_at)

    def transition(
        self,
        run_id: str,
        phase: AgentPhase,
        *,
        step: str | None = None,
        **fields: Any,
    ) -> AgentRunSnapshot:
        """迁移阶段；不允许则保留原状。"""
        snap = self.get(run_id)
        if snap is None:
            raise KeyError(f"unknown run_id={run_id}")
        if not can_transition(snap.phase, phase):
            logger.warning(
                "run store reject transition id=%s %s -> %s",
                run_id,
                snap.phase,
                phase,
            )
            return snap
        snap.phase = phase
        if step is not None:
            snap.step = step
        for key, value in fields.items():
            if hasattr(snap, key) and key not in {"run_id", "phase"}:
                setattr(snap, key, value)
        snap.updated_at = time.time()
        logger.info(
            "run store phase id=%s role=%s phase=%s step=%s",
            snap.run_id,
            snap.role,
            snap.phase,
            snap.step,
        )
        return snap
