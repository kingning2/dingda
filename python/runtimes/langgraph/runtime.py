"""LangGraph Runtime — 可控 graph run 注册表与编排生命周期。"""

from __future__ import annotations

import logging
from typing import Any

from runtime.context import RuntimeContext
from runtimes.langgraph.run_control import get_run_registry

logger = logging.getLogger("dingda.runtimes.langgraph")


class LangGraphRuntime:
    name = "langgraph"

    def __init__(self) -> None:
        self._ready = False

    def start(self, ctx: RuntimeContext) -> None:
        del ctx
        registry = get_run_registry()
        self._ready = True
        logger.info(
            "langgraph.runtime.started runs=%s",
            len(getattr(registry, "_runs", {})),
        )

    def stop(self) -> None:
        registry = get_run_registry()
        # 取消仍在跑的 run
        runs = getattr(registry, "_runs", {})
        if isinstance(runs, dict):
            for run in list(runs.values()):
                try:
                    cancelled = getattr(run, "cancelled", None)
                    if cancelled is not None:
                        cancelled.set()
                    wake = getattr(run, "wake", None)
                    if wake is not None:
                        wake.set()
                    with getattr(run, "lock", _NullLock()):
                        if hasattr(run, "status"):
                            run.status = "cancelled"
                except Exception as error:  # noqa: BLE001
                    logger.warning("langgraph.cancel_failed err=%s", error)
        self._ready = False
        logger.info("langgraph.runtime.stopped")

    def status(self) -> dict[str, Any]:
        registry = get_run_registry()
        runs = getattr(registry, "_runs", {})
        active = 0
        if isinstance(runs, dict):
            for run in runs.values():
                if getattr(run, "status", "") in ("running", "paused", "waiting_network"):
                    active += 1
        return {
            "name": self.name,
            "ready": self._ready,
            "runs": len(runs) if isinstance(runs, dict) else 0,
            "active_runs": active,
        }


class _NullLock:
    def __enter__(self) -> _NullLock:
        return self

    def __exit__(self, *args: object) -> None:
        return None
