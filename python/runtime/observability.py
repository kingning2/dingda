"""Sidecar 运行时观测 — 活跃编排、错误、WSS 摘要（Rust runtime 轮询）。"""

from __future__ import annotations

import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class RuntimeState(StrEnum):
    STOPPED = "stopped"
    STARTING = "starting"
    READY = "ready"
    RUNNING = "running"
    STOPPING = "stopping"


@dataclass
class ActiveOp:
    id: str
    kind: str
    stage: str
    detail: str
    started_ms: int


@dataclass
class RuntimeErrorRecord:
    at_ms: int
    path: str
    message: str
    trace_id: str = ""


@dataclass
class RuntimeObservability:
    """进程内 Sidecar 观测注册表（线程安全）。"""

    state: RuntimeState = RuntimeState.STOPPED
    started_at: float = field(default_factory=time.perf_counter)
    requests_total: int = 0
    requests_failed: int = 0
    _active: dict[str, ActiveOp] = field(default_factory=dict)
    _recent_errors: deque[RuntimeErrorRecord] = field(default_factory=lambda: deque(maxlen=50))
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def set_state(self, state: RuntimeState) -> None:
        with self._lock:
            self.state = state

    def begin_op(self, kind: str, *, detail: str = "", stage: str = "starting") -> str:
        op_id = uuid.uuid4().hex[:12]
        now_ms = int(time.time() * 1000)
        with self._lock:
            self._active[op_id] = ActiveOp(
                id=op_id,
                kind=kind,
                stage=stage,
                detail=detail[:240],
                started_ms=now_ms,
            )
        return op_id

    def set_stage(self, op_id: str, stage: str) -> None:
        with self._lock:
            op = self._active.get(op_id)
            if op is not None:
                op.stage = stage

    def end_op(self, op_id: str, *, error: str | None = None) -> None:
        with self._lock:
            self._active.pop(op_id, None)
        if error:
            self.record_error(path=op_id, message=error)

    def begin_request(self, path: str, handler: str, trace_id: str = "") -> str:
        with self._lock:
            self.requests_total += 1
        detail = f"{path} trace={trace_id}" if trace_id else path
        return self.begin_op(f"http:{handler}", detail=detail, stage="running")

    def end_request(self, op_id: str, *, ok: bool | None) -> None:
        if ok is False:
            with self._lock:
                self.requests_failed += 1
        self.end_op(op_id)

    def record_error(
        self,
        *,
        path: str,
        message: str,
        trace_id: str = "",
    ) -> None:
        record = RuntimeErrorRecord(
            at_ms=int(time.time() * 1000),
            path=path[:120],
            message=message[:500],
            trace_id=trace_id[:64],
        )
        with self._lock:
            self._recent_errors.appendleft(record)

    def snapshot(self) -> dict[str, Any]:
        uptime_ms = max(0, int((time.perf_counter() - self.started_at) * 1000))
        with self._lock:
            active_ops = [
                {
                    "id": op.id,
                    "kind": op.kind,
                    "stage": op.stage,
                    "detail": op.detail,
                    "started_ms": op.started_ms,
                }
                for op in self._active.values()
            ]
            recent_errors = [
                {
                    "at_ms": item.at_ms,
                    "path": item.path,
                    "message": item.message,
                    "trace_id": item.trace_id,
                }
                for item in list(self._recent_errors)[:20]
            ]
            state = self.state.value
            requests_total = self.requests_total
            requests_failed = self.requests_failed

        wss: dict[str, Any] = {"connections": []}
        try:
            from runtime.wss.manager import get_wss_manager

            wss = get_wss_manager().snapshot_sync()
        except Exception:  # noqa: BLE001
            pass

        return {
            "ok": True,
            "state": state,
            "uptime_ms": uptime_ms,
            "active_ops": active_ops,
            "recent_errors": recent_errors,
            "wss": wss,
            "stats": {
                "requests_total": requests_total,
                "requests_failed": requests_failed,
            },
        }


_registry: RuntimeObservability | None = None
_registry_lock = threading.Lock()


def get_runtime_observability() -> RuntimeObservability:
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = RuntimeObservability()
    return _registry


class track_workflow:  # noqa: N801 — 上下文管理器 API 保持 snake_case
    """上下文管理器 — 跟踪 LangGraph / 长编排。"""

    def __init__(self, kind: str, *, detail: str = "") -> None:
        self._obs = get_runtime_observability()
        self._kind = kind
        self._detail = detail
        self._op_id = ""

    def stage(self, name: str) -> None:
        if self._op_id:
            self._obs.set_stage(self._op_id, name)

    def __enter__(self) -> track_workflow:
        self._op_id = self._obs.begin_op(self._kind, detail=self._detail, stage="starting")
        return self

    def __exit__(self, exc_type, exc, _tb) -> None:
        error = str(exc) if exc is not None else None
        self._obs.end_op(self._op_id, error=error)
