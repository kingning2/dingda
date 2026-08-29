"""Worker Runtime — 后台任务槽（当前无常驻 worker，仅登记状态）。"""

from __future__ import annotations

import logging
from typing import Any

from dingda_sidecar.common.lifecycle import Component
from dingda_sidecar.runtime.context import RuntimeContext

logger = logging.getLogger("dingda.runtimes.worker")


class WorkerRuntime(Component):
    name = "worker"

    def __init__(self) -> None:
        self._ready = False

    def start(self, ctx: RuntimeContext) -> None:
        del ctx
        self._ready = True
        logger.info("worker.runtime.started")

    def stop(self) -> None:
        self._ready = False
        logger.info("worker.runtime.stopped")

    def status(self) -> dict[str, Any]:
        return {"name": self.name, "ready": self._ready, "queue": 0}
