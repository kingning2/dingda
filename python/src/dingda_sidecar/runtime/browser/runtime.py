"""Browser Runtime — Playwright / Camoufox 可用性与启停。"""

from __future__ import annotations

import logging
from typing import Any

from dingda_sidecar.common.lifecycle import Component
from dingda_sidecar.runtime.context import RuntimeContext

logger = logging.getLogger("dingda.runtimes.browser")


class BrowserRuntime(Component):
    name = "browser"

    def __init__(self) -> None:
        self._ready = False
        self._available = False

    def start(self, ctx: RuntimeContext) -> None:
        del ctx
        self._available = _probe_playwright()
        self._ready = True
        logger.info("browser.runtime.started available=%s", self._available)

    def stop(self) -> None:
        self._ready = False
        logger.info("browser.runtime.stopped")

    def status(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ready": self._ready,
            "available": self._available,
            "engine": "playwright" if self._available else "",
        }


def _probe_playwright() -> bool:
    try:
        import playwright  # noqa: F401

        return True
    except ImportError:
        return False


def browser_available() -> bool:
    """供 tools / crawlers 查询 Playwright 是否可导入。"""
    return _probe_playwright()


def browser_status() -> dict[str, Any]:
    ok = browser_available()
    return {"available": ok, "engine": "playwright" if ok else ""}
