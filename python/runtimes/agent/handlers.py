"""Agent IPC handlers — ping / complete / reply。"""

from __future__ import annotations

import logging
from typing import Any

from agent.graph.config import GraphConfig
from agent.graph.context import GraphContext
from config.settings import AiSettings
from runtime.observability import get_runtime_observability, track_workflow
from runtimes.agent.runtime import get_agent_runtime
from skills.market_research.workflow import run_reply, run_reply_with_settings

logger = logging.getLogger("dingda.runtimes.agent")


def handle_agent_ping(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    del payload, trace_id
    return {"ok": True, "pong": True}


def handle_agent_complete(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    """单轮 LLM 补全 — 不走比价 graph。"""
    if not isinstance(payload, dict):
        return {"ok": False, "message": "payload 缺失", "trace_id": trace_id}

    user = str(payload.get("user", "")).strip()
    if not user:
        return {"ok": False, "message": "user 必填", "trace_id": trace_id}

    system = str(payload.get("system") or "").strip() or None
    rt = get_agent_runtime()
    rt.begin_call()
    try:
        with track_workflow("agent_complete", detail=trace_id) as run:
            run.stage("llm")
            settings = AiSettings.from_payload({**payload, "ai_enabled": True})
            ctx = GraphContext(GraphConfig.from_ai_settings(settings))
            reply = ctx.llm(user, system=system)
    except Exception as error:  # noqa: BLE001
        get_runtime_observability().record_error(
            path="/v1/agent/complete",
            message=str(error),
            trace_id=trace_id,
        )
        logger.warning(
            "agent_complete 调用失败",
            extra={"trace_id": trace_id, "error": str(error)},
        )
        return {"ok": False, "message": f"LLM 调用失败: {error}", "trace_id": trace_id}
    finally:
        rt.end_call()
    return {"ok": True, "reply": reply, "trace_id": trace_id}


def _bind_stage(run: track_workflow):
    """把 graph on_step 接到观测 stage（仅 running 时更新，避免 done 刷屏）。"""

    def on_step(
        name: str,
        status: str,
        *,
        index: int = 0,
        total: int = 0,
        label: str = "",
        detail: str = "",
    ) -> None:
        del detail, index, total
        if status == "running":
            run.stage(label or name)
        elif status == "error":
            run.stage(f"error:{label or name}")

    return on_step


def handle_agent_reply(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"ok": False, "message": "payload 缺失"}

    user = str(payload.get("user", "")).strip()
    if not user:
        return {"ok": False, "message": "user 必填"}

    system = str(payload.get("system", "") or "")
    rt = get_agent_runtime()
    rt.begin_call()
    try:
        with track_workflow("agent_reply", detail=trace_id) as run:
            on_step = _bind_stage(run)
            if payload.get("provider_type") or payload.get("model_name"):
                settings = AiSettings.from_payload(payload)
                if not settings.api_key:
                    return {"ok": False, "message": "api_key 必填"}
                reply = run_reply_with_settings(settings, user, system=system, on_step=on_step)
            else:
                base_url = str(payload.get("base_url", "")).strip()
                api_key = str(payload.get("api_key", "")).strip()
                model = str(payload.get("model", "")).strip()
                if not base_url or not api_key or not model:
                    return {"ok": False, "message": "base_url / api_key / model / user 必填"}
                reply = run_reply(base_url, api_key, model, system, user, on_step=on_step)
    except Exception as error:
        get_runtime_observability().record_error(
            path="/v1/agent/reply",
            message=str(error),
            trace_id=trace_id,
        )
        logger.warning(
            "agent_reply 调用失败",
            extra={"trace_id": trace_id, "error": str(error)},
        )
        return {"ok": False, "message": f"agent 调用失败: {error}"}
    finally:
        rt.end_call()
    return {"ok": True, "reply": reply}
