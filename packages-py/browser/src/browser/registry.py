"""按 engine 名取出浏览器插头，避免业务里写 if。"""

from __future__ import annotations

from browser.adapters.camoufox import CamoufoxAdapter
from contracts.browser_port import BrowserPort
from core.errors import AppError

_ADAPTERS: dict[str, type[BrowserPort]] = {
    "camoufox": CamoufoxAdapter,
}


def create_browser(engine: str = "camoufox") -> BrowserPort:
    """按引擎名创建 BrowserPort 插头。"""
    cls = _ADAPTERS.get(engine)
    if cls is None:
        raise AppError("browser.engine_unsupported", f"不支持的浏览器引擎：{engine}")
    return cls()


def list_engines() -> list[str]:
    """已注册引擎名。"""
    return sorted(_ADAPTERS)
