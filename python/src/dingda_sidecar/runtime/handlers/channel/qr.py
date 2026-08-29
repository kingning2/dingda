"""Sidecar handlers：``POST /v1/channel/qr_*`` — 扫码登录启停与状态查询。

``qr_start`` / ``qr_check`` / ``qr_cancel`` 经渠道工厂拿到平台实现后驱动会话。"""

from __future__ import annotations

import logging
import time
from typing import Any

from dingda_sidecar.crawlers.core.logging import bind_log_context
from dingda_sidecar.crawlers.factory import create_channel

logger = logging.getLogger("dingda.sidecar.channel.qr")


def _channel_from_payload(payload: dict[str, Any] | None):
    platform = str((payload or {}).get("platform") or "xianyu").strip().lower() or "xianyu"
    return create_channel(platform), platform


async def handle_qr_start(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    """Contract: contracts/schema/v1/channel/sidecar/qr_start.*.schema.json"""
    with bind_log_context(trace_id=trace_id, feature="channel"):
        channel, platform = _channel_from_payload(payload)
        started = time.perf_counter()
        ok, detail, data = await channel.qrcode().start()
        duration_ms = max(0, int((time.perf_counter() - started) * 1000))
        qr = data.get("qr_base64")
        status = data.get("status", "error")
        if not qr:
            logger.warning(
                "获取二维码失败：%s duration_ms=%s",
                detail,
                duration_ms,
                extra={
                    "event": "channel.qr.failed",
                    "status": status,
                    "duration_ms": duration_ms,
                    "platform": platform,
                },
            )
        else:
            logger.info(
                "获取二维码成功 status=%s duration_ms=%s",
                status,
                duration_ms,
                extra={
                    "event": "channel.qr.started",
                    "status": status,
                    "duration_ms": duration_ms,
                    "session_id": data.get("session_id"),
                    "platform": platform,
                },
            )
        return {
            "ok": ok,
            "status": status,
            "session_id": data.get("session_id"),
            "qr_base64": qr,
            "detail": detail,
            "trace_id": trace_id,
        }


async def handle_qr_check(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    """Contract: contracts/schema/v1/channel/sidecar/qr_check.*.schema.json"""
    with bind_log_context(trace_id=trace_id, feature="channel"):
        channel, platform = _channel_from_payload(payload)
        session_id = (payload or {}).get("session_id") or ""
        if not session_id:
            return {
                "ok": False,
                "status": "error",
                "session_id": None,
                "cookies": None,
                "detail": "缺少 session_id",
                "trace_id": trace_id,
            }
        started = time.perf_counter()
        ok, detail, data = await channel.qrcode().check(session_id)
        duration_ms = max(0, int((time.perf_counter() - started) * 1000))
        status = data.get("status")
        if status != "waiting":
            logger.info(
                "%s duration_ms=%s",
                detail,
                duration_ms,
                extra={
                    "event": "channel.qr.check",
                    "status": status,
                    "duration_ms": duration_ms,
                    "session_id": session_id,
                    "platform": platform,
                },
            )
        return {
            "ok": ok,
            "status": data.get("status", "error"),
            "session_id": session_id,
            "cookies": data.get("cookies"),
            "detail": detail,
            "qr_base64": data.get("qr_base64"),
            "trace_id": trace_id,
        }


async def handle_qr_cancel(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    """Contract: contracts/schema/v1/channel/sidecar/qr_cancel.*.schema.json"""
    with bind_log_context(trace_id=trace_id, feature="channel"):
        channel, platform = _channel_from_payload(payload)
        session_id = (payload or {}).get("session_id") or ""
        started = time.perf_counter()
        ok, detail, _data = await channel.qrcode().cancel(session_id)
        duration_ms = max(0, int((time.perf_counter() - started) * 1000))
        logger.info(
            "取消扫码登录 ok=%s duration_ms=%s",
            ok,
            duration_ms,
            extra={
                "event": "channel.qr.cancelled",
                "ok": ok,
                "duration_ms": duration_ms,
                "session_id": session_id or None,
                "platform": platform,
            },
        )
        return {
            "ok": ok,
            "detail": detail,
            "trace_id": trace_id,
        }
