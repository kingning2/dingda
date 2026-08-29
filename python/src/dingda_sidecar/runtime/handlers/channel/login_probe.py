"""Sidecar handler：``POST /v1/channel/login_probe`` — 登录态探针 / HTTP 会话刷新。

- ``ali1688``：Playwright 浏览器探针
- ``xianyu``：HTTP 刷新 token，成功即在线
- ``xiaohongshu``：签名 ``/user/me`` 探活（``guest=false`` 即在线）
"""

from __future__ import annotations

import logging
import time
from typing import Any

from dingda_sidecar.crawlers.alibaba.login import verify_login_online
from dingda_sidecar.crawlers.core.logging import bind_log_context
from dingda_sidecar.crawlers.core.login.session_refresh import refresh_session_http
from dingda_sidecar.crawlers.core.platform_config import normalize_platform

logger = logging.getLogger("dingda.sidecar.channel.login_probe")


async def handle_login_probe(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    """Contract: contracts/schema/v1/channel/sidecar/login_probe.*.schema.json"""
    with bind_log_context(trace_id=trace_id, feature="channel"):
        body = payload or {}
        platform = normalize_platform(body.get("platform"))
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

        started = time.perf_counter()

        if platform in {"xianyu", "xiaohongshu"}:
            action = "HTTP 会话刷新" if platform == "xianyu" else "签名探活"
            result = refresh_session_http(platform, cookies, account_id=account_id)
            duration_ms = max(0, int((time.perf_counter() - started) * 1000))
            logger.info(
                "%s %s完成 account=%s online=%s duration_ms=%s",
                platform,
                action,
                account_id,
                result.get("online"),
                duration_ms,
            )
            return {
                **result,
                "trace_id": trace_id,
            }

        if platform != "ali1688":
            return {
                "ok": False,
                "online": False,
                "status": "unsupported_platform",
                "detail": f"登录探针暂不支持平台: {platform}",
                "trace_id": trace_id,
            }

        headed = body.get("headed")
        headed_flag = headed if isinstance(headed, bool) else None

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
