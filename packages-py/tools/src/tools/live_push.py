"""工具把浏览器直播帧推回 Agent run。

职责：
    在 `tools.cli` 子进程里，把 crawler 截图 POST 到 Server live-frame，
    供主进程 SSE 下发 browserFrame。search / product / preview 共用。

设计说明：
    - 依赖环境变量 ``DINGDA_AGENT_RUN_ID`` / ``DINGDA_API_BASE``
    - 无 run_id 时返回 None（不推帧），不打断工具
"""

from __future__ import annotations

import logging
import os
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger("dingda.tools.live_push")

LiveFrameHandler = Callable[[dict[str, Any]], Awaitable[None]]


def agent_run_id() -> str:
    """当前 Agent run id（MCP 注入）。"""
    return os.getenv("DINGDA_AGENT_RUN_ID", "").strip()


def api_base() -> str:
    """Server API Base。"""
    return (
        os.getenv("DINGDA_API_BASE", "").strip()
        or os.getenv("VITE_API_BASE_URL", "").strip()
        or "http://127.0.0.1:8787"
    ).rstrip("/")


async def post_live_frame(run_id: str, frame: dict[str, Any]) -> None:
    """POST 一帧到 ``/v1/agent/runtimes/runs/{run_id}/live-frame``。"""
    import httpx

    url = f"{api_base()}/v1/agent/runtimes/runs/{run_id}/live-frame"
    payload = {
        "url": frame.get("url") or "",
        "title": frame.get("title") or "",
        "hint": frame.get("hint"),
        "mime": frame.get("mime") or "image/jpeg",
        "image_b64": frame.get("image_b64") or "",
    }
    if not payload["image_b64"]:
        logger.warning("live frame skip empty image run=%s", run_id)
        return
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code >= 400:
                logger.warning(
                    "live frame post failed status=%s run=%s url=%s",
                    resp.status_code,
                    run_id,
                    url,
                )
    except Exception:  # noqa: BLE001
        logger.warning("live frame post failed run=%s url=%s", run_id, url, exc_info=True)


def make_live_frame_handler() -> LiveFrameHandler | None:
    """有 run_id 则返回推帧回调，否则 None。"""
    run_id = agent_run_id()
    if not run_id:
        return None

    async def on_frame(frame: dict[str, Any]) -> None:
        await post_live_frame(run_id, frame)

    return on_frame
