"""应用配置 — AI 设置与模型定义。"""

from __future__ import annotations

from typing import Any

__all__ = ["AiSettings", "ProviderKind", "ProviderSettings"]


def __getattr__(name: str) -> Any:
    if name == "ProviderKind":
        from config.models import ProviderKind

        return ProviderKind
    if name == "ProviderSettings":
        from config.models import ProviderSettings

        return ProviderSettings
    if name == "AiSettings":
        from config.settings import AiSettings

        return AiSettings
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
