"""应用配置包 — AI 设置与 Provider 模型定义。

对外经 ``__getattr__`` 延迟导出，避免配置与 LLM 工厂循环导入。"""

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
