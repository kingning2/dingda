"""Agent run 进度推送 — 经管道 Event，不再让 Rust 轮询 status。"""

from __future__ import annotations

from typing import Any

from dingda_sidecar.runtime.ipc_push import emit_event
from dingda_sidecar.runtime.langgraph.run_control import GraphRun, StepRecord

AGENT_RUN_EVENT = "agent.run"


def emit_run_progress(run: GraphRun, step: StepRecord | None = None) -> None:
    with run.lock:
        params: dict[str, Any] = {
            "run_id": run.run_id,
            "state": run.status,
            "reply": run.reply or None,
            "error": run.error or None,
            "error_kind": run.error_kind or None,
            "failed_node": run.failed_node or None,
        }
    if step is not None:
        params["step"] = step.to_dict()
    emit_event(AGENT_RUN_EVENT, params)
