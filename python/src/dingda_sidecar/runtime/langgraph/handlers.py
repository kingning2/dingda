"""Agent run IPC — start / control / status / cancel（可控 graph）。"""

from __future__ import annotations

import logging
import threading
from typing import Any

from dingda_sidecar.runtime.langgraph.push import emit_run_progress
from dingda_sidecar.runtime.langgraph.run_control import (
    GraphRun,
    NodeModel,
    deep_copy_state,
    get_run_registry,
    loads_state,
    new_run_id,
    parse_node_models,
)
from dingda_sidecar.runtime.langgraph.step_runner import (
    PRICE_COMPARE_STEPS,
    build_initial_state,
    make_default_model,
    run_steps,
)
from dingda_sidecar.runtime.observability import get_runtime_observability, track_workflow

logger = logging.getLogger("dingda.runtimes.langgraph")


def _redact_model(model: NodeModel | None) -> dict[str, str]:
    if model is None:
        return {}
    key = model.api_key or ""
    masked = f"{key[:4]}***{key[-2:]}" if len(key) > 8 else ("***" if key else "")
    return {
        "node": model.node,
        "model": model.model,
        "base_url": model.base_url,
        "account_id": model.account_id,
        "api_key": masked,
    }


def _spawn(run: GraphRun) -> None:
    def _target() -> None:
        with track_workflow("agent_run", detail=run.run_id) as tracked:
            tracked.stage("running")
            run_steps(run)
            tracked.stage(run.status)

    threading.Thread(target=_target, name=f"graph-run-{run.run_id[:8]}", daemon=True).start()


def handle_agent_run_start(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"ok": False, "run_id": "", "state": "failed", "message": "payload 缺失"}

    user = str(payload.get("user") or "").strip()
    if not user:
        return {"ok": False, "run_id": "", "state": "failed", "message": "user 必填"}

    run_id = str(payload.get("run_id") or "").strip() or new_run_id()
    system = str(payload.get("system") or "")
    kind = str(payload.get("kind") or "price_compare")
    raw_node_models = payload.get("node_models")
    node_models = parse_node_models(raw_node_models if isinstance(raw_node_models, list) else None)
    default = make_default_model(
        base_url=str(payload.get("default_base_url") or ""),
        api_key=str(payload.get("default_api_key") or ""),
        model=str(payload.get("default_model") or ""),
    )

    initial = build_initial_state(user)
    channel_account_id = str(payload.get("channel_account_id") or "").strip()
    raw_cookies = payload.get("cookies")
    if channel_account_id and isinstance(raw_cookies, list) and raw_cookies:
        initial["account_id"] = channel_account_id
        initial["cookies"] = raw_cookies
        logger.info(
            "agent_run.crawl_channel run_id=%s account=%s cookies=%s",
            run_id,
            channel_account_id,
            len(raw_cookies),
        )
    else:
        logger.warning(
            "agent_run.crawl_channel.missing run_id=%s account=%s cookies=%s",
            run_id,
            channel_account_id or "-",
            len(raw_cookies) if isinstance(raw_cookies, list) else 0,
        )
    resume_node = str(payload.get("resume_node") or "").strip()
    resume_state = loads_state(str(payload.get("resume_state_json") or "") or None)
    cursor = 0
    completed: list[str] = []
    state_before: dict[str, dict[str, Any]] = {}
    if resume_state is not None and resume_node:
        if resume_node not in PRICE_COMPARE_STEPS:
            return {
                "ok": False,
                "run_id": run_id,
                "state": "failed",
                "message": f"无效 resume_node: {resume_node}",
            }
        initial = deep_copy_state(resume_state)
        cursor = PRICE_COMPARE_STEPS.index(resume_node)
        completed = list(PRICE_COMPARE_STEPS[:cursor])
        state_before[resume_node] = deep_copy_state(resume_state)

    run = GraphRun(
        run_id=run_id,
        kind=kind,
        user=user,
        system=system,
        initial_state=deep_copy_state(build_initial_state(user)),
        state=initial,
        node_models=node_models,
        default_model=default,
        steps_order=PRICE_COMPARE_STEPS,
        cursor=cursor,
        completed_nodes=completed,
        state_before=state_before,
    )
    get_run_registry().create(run)
    emit_run_progress(run)
    _spawn(run)
    logger.info(
        "agent_run.start run_id=%s kind=%s user=%s resume_node=%s nodes=%s default=%s",
        run_id,
        kind,
        user[:200],
        resume_node or "-",
        [_redact_model(m) for m in node_models.values()],
        _redact_model(default),
        extra={"trace_id": trace_id, "run_id": run_id, "feature": "graph"},
    )
    return {"ok": True, "run_id": run_id, "state": run.status}


def handle_agent_run_control(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"ok": False, "run_id": "", "state": "failed", "message": "payload 缺失"}

    run_id = str(payload.get("run_id") or "").strip()
    action = str(payload.get("action") or "").strip().lower()
    run = get_run_registry().get(run_id)
    if run is None:
        logger.warning("agent_run.control miss run_id=%s action=%s", run_id, action)
        return {"ok": False, "run_id": run_id, "state": "failed", "message": "run 不存在"}

    node = str(payload.get("node") or "").strip()
    logger.info(
        "agent_run.control run_id=%s action=%s node=%s status=%s cursor=%s/%s completed=%s",
        run_id,
        action,
        node or "-",
        run.status,
        run.cursor,
        len(run.steps_order),
        list(run.completed_nodes),
        extra={"trace_id": trace_id or run_id, "run_id": run_id, "feature": "graph"},
    )
    raw_model = payload.get("node_model")
    override: NodeModel | None = None
    if isinstance(raw_model, dict):
        override = NodeModel(
            node=str(raw_model.get("node") or node or ""),
            base_url=str(raw_model.get("base_url") or ""),
            api_key=str(raw_model.get("api_key") or ""),
            model=str(raw_model.get("model") or ""),
            account_id=str(raw_model.get("account_id") or ""),
            provider_type=str(raw_model.get("provider_type") or ""),
        )

    if action == "pause":
        run.paused.set()
        run.wake.set()
        with run.lock:
            if run.status == "running":
                run.status = "paused"
        emit_run_progress(run)
        return {"ok": True, "run_id": run_id, "state": run.status}

    if action == "continue":
        with run.lock:
            run.pending_action = "continue"
        run.paused.clear()
        run.wake.set()
        return {"ok": True, "run_id": run_id, "state": "running"}

    if action == "restart":
        with run.lock:
            run.pending_action = "restart"
            run.pending_node_model = override
        run.paused.clear()
        # if failed, respawn
        if run.status in ("failed", "cancelled", "completed"):
            with run.lock:
                run.status = "running"
                run.cancelled.clear()
                run.error = ""
                run.error_kind = ""
                run.failed_node = ""
            _spawn(run)
        run.wake.set()
        return {"ok": True, "run_id": run_id, "state": "running"}

    if action == "seek":
        if not node:
            return {"ok": False, "run_id": run_id, "state": run.status, "message": "seek 需要 node"}
        if node not in run.steps_order:
            return {
                "ok": False,
                "run_id": run_id,
                "state": run.status,
                "message": f"未知节点 {node}",
            }
        # allow seek to completed or failed node
        allowed = set(run.completed_nodes) | ({run.failed_node} if run.failed_node else set())
        if node not in allowed and node not in run.state_before and node != run.steps_order[0]:
            return {
                "ok": False,
                "run_id": run_id,
                "state": run.status,
                "message": f"节点尚未跑过: {node}",
            }
        with run.lock:
            run.pending_action = "seek"
            run.pending_seek_node = node
            run.pending_node_model = override
            run.cancelled.clear()
        if run.status in ("failed", "cancelled", "completed"):
            with run.lock:
                run.status = "running"
            _spawn(run)
        run.paused.clear()
        run.wake.set()
        return {"ok": True, "run_id": run_id, "state": "running"}

    return {"ok": False, "run_id": run_id, "state": run.status, "message": f"未知 action: {action}"}


def handle_agent_run_status(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    del trace_id
    if not isinstance(payload, dict):
        return {"ok": False, "run_id": "", "state": "failed", "message": "payload 缺失"}
    run_id = str(payload.get("run_id") or "").strip()
    since = int(payload.get("since_index") or 0)
    run = get_run_registry().get(run_id)
    if run is None:
        return {"ok": False, "run_id": run_id, "state": "failed", "message": "run 不存在"}
    snap = run.snapshot(since_index=since)
    return snap


def handle_agent_run_cancel(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    del trace_id
    if not isinstance(payload, dict):
        return {"ok": False, "run_id": "", "state": "failed", "message": "payload 缺失"}
    run_id = str(payload.get("run_id") or "").strip()
    run = get_run_registry().get(run_id)
    if run is None:
        return {"ok": False, "run_id": run_id, "state": "failed", "message": "run 不存在"}
    run.cancelled.set()
    run.paused.clear()
    run.wake.set()
    with run.lock:
        run.status = "cancelled"
    emit_run_progress(run)
    get_runtime_observability().record_error(
        path="/v1/agent/run/cancel",
        message=f"cancelled {run_id}",
        trace_id=run_id,
    )
    return {"ok": True, "run_id": run_id, "state": "cancelled"}
