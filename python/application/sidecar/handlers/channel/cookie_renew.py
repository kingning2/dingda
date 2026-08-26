"""Sidecar handler：``POST /v1/channel/cookie_renew`` — 按渠道工厂分发登录续期。

解析平台与 Cookie，调用对应续期实现并返回结构化结果与耗时。"""

from __future__ import annotations

import logging
import time
from typing import Any

from crawlers.core.logging import bind_log_context
from crawlers.core.platform_config import normalize_platform
from crawlers.factory import create_channel

logger = logging.getLogger("dingda.sidecar.channel.cookie_renew")


async def handle_cookie_renew(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    """Contract: contracts/schema/v1/channel/sidecar/cookie_renew.*.schema.json"""
    with bind_log_context(trace_id=trace_id, feature="channel"):
        body = payload or {}
        account_id = str(body.get("account_id") or "").strip()
        cookies = body.get("cookies")
        if not account_id or not isinstance(cookies, list):
            return {
                "ok": False,
                "status": "error",
                "cookies": None,
                "detail": "缺少 account_id 或 cookies",
                "trace_id": trace_id,
            }

        platform = normalize_platform(body.get("platform"))
        channel = create_channel(platform)
        punish_url = str(body.get("punish_url") or "").strip() or None
        started = time.perf_counter()
        ok, detail, data = await channel.renew_cookies(
            cookies,
            account_id=account_id,
            punish_url=punish_url,
        )
        duration_ms = max(0, int((time.perf_counter() - started) * 1000))
        logger.info(
            "Cookie 浏览器续期完成 status=%s duration_ms=%s account=%s platform=%s",
            data.get("status", "error"),
            duration_ms,
            account_id,
            platform,
            extra={
                "event": "channel.cookie_renew.completed",
                "status": data.get("status", "error"),
                "duration_ms": duration_ms,
                "account_id": account_id,
                "platform": platform,
            },
        )
        return {
            "ok": ok,
            "status": data.get("status", "error"),
            "cookies": data.get("cookies"),
            "detail": detail,
            "trace_id": trace_id,
        }
