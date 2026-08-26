"""Sidecar handler：``POST /v1/channel/login_probe`` — 1688 Playwright 登录态探针。

校验平台后调用 ``verify_login_online``，供 Rust 判断 Cookie 是否仍有效。"""

from __future__ import annotations

import logging
import time
from typing import Any

from crawlers.alibaba.login import verify_login_online
from crawlers.core.logging import bind_log_context
from crawlers.core.platform_config import normalize_platform

logger = logging.getLogger("dingda.sidecar.channel.login_probe")


async def handle_login_probe(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    """Contract: contracts/schema/v1/channel/sidecar/login_probe.*.schema.json"""
    with bind_log_context(trace_id=trace_id, feature="channel"):
        body = payload or {}
        platform = normalize_platform(body.get("platform"))
        if platform != "ali1688":
            return {
                "ok": False,
                "online": False,
                "status": "unsupported_platform",
                "detail": f"登录探针暂不支持平台: {platform}",
                "trace_id": trace_id,
            }

        account_id = str(body.get("account_id") or "").strip()
        cookies = body.get("cookies")
        if not account_id or not isinstance(cookies, list):
            return {
                "ok": False,
                "online": False,
                "status": "error",
                "detail": "缺少 account_id / cookies",
                "trace_id": trace_id,
            }

        headed = body.get("headed")
        headed_flag = headed if isinstance(headed, bool) else None

        started = time.perf_counter()
        try:
            result = await verify_login_online(
                account_id=account_id,
                cookies=cookies,
                headed=headed_flag,
            )
        except Exception as error:  # noqa: BLE001
            duration_ms = max(0, int((time.perf_counter() - started) * 1000))
            logger.exception(
                "1688 登录探针失败 account=%s duration_ms=%s",
                account_id,
                duration_ms,
            )
            return {
                "ok": False,
                "online": False,
                "status": "error",
                "detail": str(error),
                "trace_id": trace_id,
            }

        duration_ms = max(0, int((time.perf_counter() - started) * 1000))
        logger.info(
            "1688 登录探针 sidecar 完成 account=%s online=%s duration_ms=%s",
            account_id,
            result.get("online"),
            duration_ms,
        )
        return {
            **result,
            "trace_id": trace_id,
        }
