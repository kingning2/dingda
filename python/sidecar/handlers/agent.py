"""LangGraph agent 接口 — /v1/agent/ping 与 /v1/agent/reply。"""

from __future__ import annotations

import logging
from typing import Any

from sidecar.agents.graph import run_reply

logger = logging.getLogger("dingda.sidecar")


def handle_agent_ping(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    """Agent 探活：sidecar 已启动即返回 ok。"""
    del payload, trace_id
    return {"ok": True, "pong": True}


def handle_agent_reply(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    """跑 LangGraph agent，返回最终回复。"""
    if not isinstance(payload, dict):
        return {"ok": False, "message": "payload 缺失"}
    base_url = str(payload.get("base_url", "")).strip()
    api_key = str(payload.get("api_key", "")).strip()
    model = str(payload.get("model", "")).strip()
    user = str(payload.get("user", "")).strip()
    system = str(payload.get("system", "") or "")
    if not base_url or not api_key or not model or not user:
        return {"ok": False, "message": "base_url / api_key / model / user 必填"}
    try:
        reply = run_reply(base_url, api_key, model, system, user)
    except Exception as error:
        logger.warning(
            "agent_reply 调用失败",
            extra={"trace_id": trace_id, "error": str(error)},
        )
        return {"ok": False, "message": f"agent 调用失败: {error}"}
    return {"ok": True, "reply": reply}
