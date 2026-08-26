"""Agent Runtime — ping / complete / reply 请求生命周期。"""

from __future__ import annotations

import logging
import threading
from typing import Any

from runtime.context import RuntimeContext

logger = logging.getLogger("dingda.runtimes.agent")


class AgentRuntime:
    name = "agent"

    def __init__(self) -> None:
        self._ready = False
        self._lock = threading.Lock()
        self._inflight = 0

    def start(self, ctx: RuntimeContext) -> None:
        del ctx
        self._ready = True
        logger.info("agent.runtime.started")

    def stop(self) -> None:
        self._ready = False
        logger.info("agent.runtime.stopped inflight=%s", self._inflight)

    def begin_call(self) -> None:
        with self._lock:
            self._inflight += 1

    def end_call(self) -> None:
        with self._lock:
            self._inflight = max(0, self._inflight - 1)

    def status(self) -> dict[str, Any]:
        with self._lock:
            inflight = self._inflight
        return {"name": self.name, "ready": self._ready, "inflight": inflight}


_RUNTIME: AgentRuntime | None = None


def get_agent_runtime() -> AgentRuntime:
    global _RUNTIME
    if _RUNTIME is None:
        _RUNTIME = AgentRuntime()
    return _RUNTIME
