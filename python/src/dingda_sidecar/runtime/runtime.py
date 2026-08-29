"""宿主 AppRuntime — 协调各子 runtime 启停。"""

from __future__ import annotations

import logging
import threading
from typing import Any

from dingda_sidecar.common.lifecycle import Component
from dingda_sidecar.runtime.agent.runtime import get_agent_runtime
from dingda_sidecar.runtime.browser import BrowserRuntime
from dingda_sidecar.runtime.context import RuntimeContext
from dingda_sidecar.runtime.knowledge.runtime import get_knowledge_runtime
from dingda_sidecar.runtime.langgraph import LangGraphRuntime
from dingda_sidecar.runtime.worker import WorkerRuntime
from dingda_sidecar.runtime.wss.runtime import get_wss_runtime

logger = logging.getLogger("dingda.runtime.app")

_LOCK = threading.Lock()
_APP: AppRuntime | None = None


class AppRuntime:
    """进程内唯一宿主 runtime。"""

    def __init__(self) -> None:
        self.ctx = RuntimeContext(app=None)
        self.ctx.app = self
        self.agent = get_agent_runtime()
        self.browser = BrowserRuntime()
        self.wss = get_wss_runtime()
        self.langgraph = LangGraphRuntime()
        self.worker = WorkerRuntime()
        self.knowledge = get_knowledge_runtime()
        self._children: tuple[Component, ...] = (
            self.agent,
            self.browser,
            self.wss,
            self.langgraph,
            self.worker,
            self.knowledge,
        )
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        for child in self._children:
            child.start(self.ctx)
            logger.info(
                "sub_runtime.started name=%s",
                child.name,
                extra={"event": "runtime.child.started", "feature": "runtime"},
            )
        self._started = True

    def stop(self) -> None:
        if not self._started:
            return
        for child in reversed(self._children):
            try:
                child.stop()
            except Exception as error:  # noqa: BLE001
                logger.warning(
                    "sub_runtime.stop_failed name=%s err=%s",
                    child.name,
                    error,
                )
        self._started = False

    def status(self) -> dict[str, Any]:
        return {
            "started": self._started,
            "children": {
                child.name: {
                    "state": child.state(),
                    **child.status(),
                }
                for child in self._children
            },
        }


def get_app_runtime() -> AppRuntime:
    global _APP
    with _LOCK:
        if _APP is None:
            _APP = AppRuntime()
        return _APP
