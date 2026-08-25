"""Sidecar handler：``POST /v1/channel/search`` — 渠道关键词搜索（1688 / 闲鱼）。

按平台选择 fetch 实现，统一返回商品/offer 列表给 Rust。"""

from __future__ import annotations

import logging
import time
from typing import Any

from crawlers.alibaba import fetch_search as fetch_ali1688_search
from crawlers.core.logging import bind_log_context
from crawlers.core.platform_config import normalize_platform
from crawlers.xianyu import fetch_search as fetch_xianyu_search

logger = logging.getLogger("dingda.sidecar.channel.search")

_SEARCH_FETCHERS = {
    "ali1688": fetch_ali1688_search,
    "xianyu": fetch_xianyu_search,
}


async def handle_search(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    """Contract: contracts/schema/v1/channel/sidecar/search.*.schema.json"""
    with bind_log_context(trace_id=trace_id, feature="channel"):
        body = payload or {}
        platform = normalize_platform(body.get("platform"))
        fetch_search = _SEARCH_FETCHERS.get(platform)
        if fetch_search is None:
            return {
                "ok": False,
                "status": "error",
                "keyword": "",
                "total": 0,
                "total_before_filter": 0,
                "offers": [],
                "detail": f"搜索暂不支持平台: {platform}",
                "trace_id": trace_id,
            }

        account_id = str(body.get("account_id") or "").strip()
        keyword = str(body.get("keyword") or "").strip()
        cookies = body.get("cookies")
        if not account_id or not keyword or not isinstance(cookies, list):
            return {
                "ok": False,
                "status": "error",
                "keyword": keyword,
                "total": 0,
                "total_before_filter": 0,
                "offers": [],
                "detail": "缺少 account_id / keyword / cookies",
                "trace_id": trace_id,
            }

        max_results = body.get("max_results")
        if not isinstance(max_results, int) or max_results <= 0:
            max_results = 20
        max_results = min(max_results, 120)
        headed = body.get("headed")
        headed_flag = headed if isinstance(headed, bool) else None

        started = time.perf_counter()
        try:
            result = await fetch_search(
                keyword,
                account_id=account_id,
                cookies=cookies,
                max_results=max_results,
                headed=headed_flag if headed_flag is not None else True,
            )
        except Exception as error:  # noqa: BLE001
            duration_ms = max(0, int((time.perf_counter() - started) * 1000))
            logger.exception(
                "%s 搜索失败 account=%s duration_ms=%s",
                platform,
                account_id,
                duration_ms,
            )
            return {
                "ok": False,
                "status": "error",
                "keyword": keyword,
                "total": 0,
                "total_before_filter": 0,
                "offers": [],
                "detail": str(error),
                "trace_id": trace_id,
            }

        duration_ms = max(0, int((time.perf_counter() - started) * 1000))
        logger.info(
            "%s 搜索完成 account=%s status=%s total=%s duration_ms=%s",
            platform,
            account_id,
            result.get("status"),
            result.get("total"),
            duration_ms,
            extra={
                "event": "channel.search.completed",
                "platform": platform,
                "account_id": account_id,
                "status": result.get("status"),
                "total": result.get("total"),
                "duration_ms": duration_ms,
            },
        )
        return {
            **result,
            "trace_id": trace_id,
        }
