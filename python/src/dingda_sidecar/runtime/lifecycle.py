"""Runtime 生命周期 — 启动/停止钩子。

在 serve 前后登记观测状态，并启停 ``AppRuntime`` 子运行时。"""

from __future__ import annotations

import logging

from dingda_sidecar.runtime.observability import get_runtime_observability
from dingda_sidecar.runtime.runtime import get_app_runtime
from dingda_sidecar.runtime.state import RuntimeState

logger = logging.getLogger("dingda.runtime")


class RuntimeLifecycle:
    """Sidecar 进程内生命周期状态（与 Rust PythonState 语义对齐）。"""

    def __init__(self) -> None:
        self._obs = get_runtime_observability()
        self._obs.set_state(RuntimeState.STOPPED)

    @property
    def state(self) -> RuntimeState:
        return self._obs.state

    def on_starting(self) -> None:
        self._obs.set_state(RuntimeState.STARTING)
        logger.debug("runtime starting", extra={"event": "runtime.starting", "feature": "runtime"})

    def on_ready(self) -> None:
        get_app_runtime().start()
        self._obs.set_state(RuntimeState.READY)
        logger.debug("runtime ready", extra={"event": "runtime.ready", "feature": "runtime"})

    def on_running(self) -> None:
        self._obs.set_state(RuntimeState.RUNNING)

    def on_stopping(self) -> None:
        self._obs.set_state(RuntimeState.STOPPING)
        logger.debug("runtime stopping", extra={"event": "runtime.stopping", "feature": "runtime"})
        get_app_runtime().stop()

    def on_stopped(self) -> None:
        self._obs.set_state(RuntimeState.STOPPED)
