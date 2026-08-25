"""Agent IPC — 支持多 Provider 与 AiSettings。

处理 ping / complete / reply，把请求交给比价等工作流并记录观测指标。"""

from __future__ import annotations

import logging
from typing import Any

from config.settings import AiSettings
from graph.core.config import GraphConfig
from graph.core.context import GraphContext
from graph.workflows.price_compare import run_reply, run_reply_with_settings
from runtime.observability import get_runtime_observability, track_workflow

logger = logging.getLogger("dingda.runtime.agent")


def handle_agent_ping(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    del payload, trace_id
    return {"ok": True, "pong": True}


def handle_agent_complete(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    """单轮 LLM 补全 — 监控关键词/决策等，不走比价 graph。"""
    if not isinstance(payload, dict):
        return {"ok": False, "message": "payload 缺失", "trace_id": trace_id}

    user = str(payload.get("user", "")).strip()
    if not user:
        return {"ok": False, "message": "user 必填", "trace_id": trace_id}

    system = str(payload.get("system") or "").strip() or None
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
    return {"ok": True, "reply": reply, "trace_id": trace_id}


def handle_agent_reply(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"ok": False, "message": "payload 缺失"}

    user = str(payload.get("user", "")).strip()
    if not user:
        return {"ok": False, "message": "user 必填"}

    system = str(payload.get("system", "") or "")

    try:
        with track_workflow("agent_reply", detail=trace_id) as run:
            if payload.get("provider_type") or payload.get("model_name"):
                run.stage("price_compare")
                settings = AiSettings.from_payload(payload)
                if not settings.api_key:
                    return {"ok": False, "message": "api_key 必填"}
                reply = run_reply_with_settings(settings, user, system=system)
            else:
                run.stage("price_compare")
                base_url = str(payload.get("base_url", "")).strip()
                api_key = str(payload.get("api_key", "")).strip()
                model = str(payload.get("model", "")).strip()
                if not base_url or not api_key or not model:
                    return {"ok": False, "message": "base_url / api_key / model / user 必填"}
                reply = run_reply(base_url, api_key, model, system, user)
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
    return {"ok": True, "reply": reply}
