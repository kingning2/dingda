"""Knowledge Runtime — 知识服务进程内单例生命周期。"""

from __future__ import annotations

import logging
from typing import Any

from dingda_sidecar.common.lifecycle import Component
from dingda_sidecar.runtime.context import RuntimeContext

logger = logging.getLogger("dingda.runtimes.knowledge")


class KnowledgeRuntime(Component):
    name = "knowledge"

    def __init__(self) -> None:
        self._ready = False
        self._service: Any = None

    @property
    def service(self) -> Any:
        if self._service is None:
            from dingda_sidecar.agent.knowledge import KnowledgeService

            self._service = KnowledgeService()
        return self._service

    def start(self, ctx: RuntimeContext) -> None:
        del ctx
        _ = self.service
        self._ready = True
        logger.info("knowledge.runtime.started")

    def stop(self) -> None:
        self._service = None
        self._ready = False
        logger.info("knowledge.runtime.stopped")

    def status(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ready": self._ready,
            "loaded": self._service is not None,
        }


_RUNTIME: KnowledgeRuntime | None = None


def get_knowledge_runtime() -> KnowledgeRuntime:
    global _RUNTIME
    if _RUNTIME is None:
        _RUNTIME = KnowledgeRuntime()
    return _RUNTIME


def get_knowledge_service() -> Any:
    return get_knowledge_runtime().service
