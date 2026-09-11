"""Agent 运行直播帧总线（跨 MCP 子进程 → Server SSE）。

职责：
    按 run_id 登记队列；MCP ``preview`` 经 HTTP 投帧，spawn 侧 drain 进 SSE。

设计说明：
    - MCP 与 FastAPI 不在同进程，不能靠内存回调直连
    - 队列有界，丢最旧帧，避免阻塞浏览器推帧

使用示例：
    open_run("run-1")
    push_frame("run-1", {"type": "browserFrame", ...})
    for event in drain("run-1"): ...
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict, deque
from typing import Any

logger = logging.getLogger("dingda.cli.live.hub")

_MAX_QUEUED = 24

_queues: defaultdict[str, deque[dict[str, Any]]] = defaultdict(
    lambda: deque(maxlen=_MAX_QUEUED)
)
_locks: dict[str, asyncio.Lock] = {}


def open_run(run_id: str) -> None:
    """为一次 CLI run 打开帧队列。"""
    key = run_id.strip()
    if not key:
        return
    _queues[key].clear()
    logger.info("live hub open run=%s", key)


def close_run(run_id: str) -> None:
    """关闭并丢弃队列。"""
    key = run_id.strip()
    _queues.pop(key, None)
    _locks.pop(key, None)
    logger.debug("live hub close run=%s", key)


def push_frame(run_id: str, event: dict[str, Any]) -> None:
    """投递一帧事件（同步，供 HTTP handler 调用）。"""
    key = run_id.strip()
    if not key or key not in _queues:
        logger.warning("live hub drop frame unknown run=%s", key or "-")
        return
    q = _queues[key]
    if len(q) >= _MAX_QUEUED:
        q.popleft()
    q.append(event)


def drain(run_id: str) -> list[dict[str, Any]]:
    """取出当前积压帧。"""
    key = run_id.strip()
    q = _queues.get(key)
    if not q:
        return []
    out = list(q)
    q.clear()
    return out
