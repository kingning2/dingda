"""Auto-generated from contracts/schema."""

from __future__ import annotations

from typing import Literal, TypedDict


RuntimeComponentState = Literal[
    "created",
    "starting",
    "running",
    "degraded",
    "stopping",
    "stopped",
    "failed",
]


class RuntimeEventError(TypedDict, total=False):
    event_id: str
    occurred_at: str
    kind: str
    stage: str
    message: str
    detail: str


class RuntimeEventSidecarRestarted(TypedDict, total=False):
    event_id: str
    occurred_at: str
    port: int
    attempt: int
    reason: str


class RuntimeLogEntry(TypedDict, total=False):
    schema_version: str
    timestamp: str
    level: str
    source: str
    logger: str
    message: str
    event: str
    feature: str
    trace_id: str
    task_id: str
    tenant_id: str
    attributes: str
    exception: str
