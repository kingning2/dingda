"""DOM 修复门闸与限流。"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

logger = logging.getLogger("dingda.crawler.repair.gates")

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()
_AI_CALLS = 0
_AI_BUDGET = int(os.getenv("DINGDA_DOM_REPAIR_BUDGET", "20") or "20")
_MAX_ROUNDS = int(os.getenv("DINGDA_DOM_REPAIR_ROUNDS", "3") or "3")


def repair_enabled() -> bool:
    """``DINGDA_DOM_REPAIR=0`` 关闭 AI 修。"""
    return (os.getenv("DINGDA_DOM_REPAIR", "1") or "1").strip() not in {"0", "false", "False"}


def max_rounds() -> int:
    return max(1, _MAX_ROUNDS)


def try_acquire_platform(platform: str) -> bool:
    """每平台同时仅一个 AI repair。"""
    with _LOCKS_GUARD:
        lock = _LOCKS.setdefault(platform, threading.Lock())
    got = lock.acquire(blocking=False)
    if not got:
        logger.info("repair busy platform=%s", platform)
    return got


def release_platform(platform: str) -> None:
    with _LOCKS_GUARD:
        lock = _LOCKS.get(platform)
    if lock is not None and lock.locked():
        lock.release()


def consume_ai_budget() -> bool:
    """进程级 AI 调用预算。"""
    global _AI_CALLS
    if _AI_CALLS >= _AI_BUDGET:
        logger.warning("repair ai budget exhausted used=%s budget=%s", _AI_CALLS, _AI_BUDGET)
        return False
    _AI_CALLS += 1
    return True


def looks_risk_text(text: str) -> bool:
    blob = text or ""
    return any(
        token in blob
        for token in (
            "拖动下方滑块",
            "请按住滑块",
            "安全验证",
            "验证码",
            "FAIL_SYS_USER_VALIDATE",
            "被挤爆",
        )
    )
