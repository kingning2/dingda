"""Sidecar handler：``POST /v1/channel/sessions_batch`` — 单浏览器多标签批量探针/续期。"""

from __future__ import annotations

import logging
import time
from typing import Any

from dingda_sidecar.crawlers.core.logging import bind_log_context
from dingda_sidecar.crawlers.core.login.batch_session import batch_sessions

logger = logging.getLogger("dingda.sidecar.channel.sessions_batch")


async def handle_sessions_batch(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    with bind_log_context(trace_id=trace_id, feature="channel"):
        body = payload or {}
        targets = body.get("targets")
        if not isinstance(targets, list) or len(targets) == 0:
            return {
                "ok": False,
                "results": [],
                "detail": "缺少 targets",
                "trace_id": trace_id,
            }

        refresh = bool(body.get("refresh"))
        started = time.perf_counter()
        try:
            results = await batch_sessions(targets, refresh=refresh)
        except Exception as error:  # noqa: BLE001
            duration_ms = max(0, int((time.perf_counter() - started) * 1000))
            logger.exception("batch session 失败 duration_ms=%s", duration_ms)
            return {
                "ok": False,
                "results": [],
                "detail": str(error),
                "trace_id": trace_id,
            }

        duration_ms = max(0, int((time.perf_counter() - started) * 1000))
        online_count = sum(1 for item in results if item.get("online"))
        logger.info(
            "batch session sidecar 完成 tabs=%s online=%s refresh=%s duration_ms=%s",
            len(results),
            online_count,
            refresh,
            duration_ms,
        )
        return {
            "ok": True,
            "results": results,
            "detail": None,
            "trace_id": trace_id,
        }
