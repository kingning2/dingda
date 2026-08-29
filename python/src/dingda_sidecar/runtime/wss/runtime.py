"""WSS Runtime — 多账号 WebSocket 连接生命周期（原 runtime.wss）。"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from dingda_sidecar.common.lifecycle import Component
from dingda_sidecar.runtime.context import RuntimeContext
from dingda_sidecar.runtime.wss.manager import WssManager

logger = logging.getLogger("dingda.runtimes.wss")


class WssRuntime(Component):
    name = "wss"

    def __init__(self) -> None:
        self._ready = False
        self._manager: WssManager | None = None

    @property
    def manager(self) -> WssManager:
        if self._manager is None:
            self._manager = WssManager()
        return self._manager

    def start(self, ctx: RuntimeContext) -> None:
        del ctx
        _ = self.manager
        self._ready = True
        logger.info("wss.runtime.started")

    def stop(self) -> None:
        manager = self._manager
        if manager is not None and getattr(manager, "_connections", None):
            try:
                from dingda_sidecar.runtime.dispatch import get_async_loop

                loop = get_async_loop()
                fut = asyncio.run_coroutine_threadsafe(self._disconnect_all(manager), loop)
                fut.result(timeout=30)
            except Exception as error:  # noqa: BLE001
                logger.warning("wss.runtime.stop_failed err=%s", error)
        self._ready = False
        logger.info("wss.runtime.stopped")

    async def _disconnect_all(self, manager: WssManager) -> None:
        ids = list(getattr(manager, "_connections", {}).keys())
        for account_id in ids:
            try:
                await manager.disconnect(account_id)
            except Exception as error:  # noqa: BLE001
                logger.warning("wss.disconnect_failed account=%s err=%s", account_id, error)

    def status(self) -> dict[str, Any]:
        summary: dict[str, Any] = {}
        manager = self._manager
        if manager is not None:
            summary = dict(manager.snapshot_sync() or {})
        return {"name": self.name, "ready": self._ready, **summary}


_RUNTIME: WssRuntime | None = None


def get_wss_runtime() -> WssRuntime:
    global _RUNTIME
    if _RUNTIME is None:
        _RUNTIME = WssRuntime()
    return _RUNTIME


def get_wss_manager() -> WssManager:
    """进程内唯一 WssManager，经 WssRuntime 持有。"""
    return get_wss_runtime().manager
