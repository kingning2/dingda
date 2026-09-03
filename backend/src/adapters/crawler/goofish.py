"""闲鱼（goofish_cli）适配器。"""

from __future__ import annotations

import importlib
import os
from types import ModuleType

from src.adapters.registry import import_vendor, is_vendor_installed


def configure_goofish_runtime() -> None:
    """Dingda 接管浏览器续期：禁止 goofish_cli 自动弹 Playwright Chrome。"""
    os.environ.setdefault("GOOFISH_AUTO_REFRESH_TOKEN", "0")


def get_goofish_session_factory() -> ModuleType:
    import_vendor("goofish_cli")
    return importlib.import_module("goofish_cli.core.session")


def is_goofish_available() -> bool:
    return is_vendor_installed("goofish_cli")
