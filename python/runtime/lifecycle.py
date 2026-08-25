"""Runtime 生命周期 — 启动/停止钩子。"""

from __future__ import annotations

import logging

from runtime.observability import RuntimeState, get_runtime_observability

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

        self._obs.set_state(RuntimeState.READY)

        logger.debug("runtime ready", extra={"event": "runtime.ready", "feature": "runtime"})

    def on_running(self) -> None:

        self._obs.set_state(RuntimeState.RUNNING)

    def on_stopping(self) -> None:

        self._obs.set_state(RuntimeState.STOPPING)

        logger.debug("runtime stopping", extra={"event": "runtime.stopping", "feature": "runtime"})

    def on_stopped(self) -> None:

        self._obs.set_state(RuntimeState.STOPPED)
