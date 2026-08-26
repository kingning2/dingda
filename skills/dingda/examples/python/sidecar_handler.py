"""Example: Python sidecar handler (Python ← Rust only).

Real handlers live in python/application/sidecar/handlers/;
platform login in python/crawlers/<platform>/login/.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("dingda.examples.sidecar")


def handle_agent_ping(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    """POST /v1/agent/ping — contract-driven request/response."""
    logger.info("agent_ping", extra={"trace_id": trace_id})
    _ = payload
    return {"ok": True, "trace_id": trace_id}
