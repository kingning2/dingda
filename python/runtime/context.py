"""Runtime 共享上下文 — 子 runtime 启动时注入。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from runtime.runtime import AppRuntime


@dataclass
class RuntimeContext:
    """进程级共享上下文（配置、宿主引用、扩展槽）。"""

    app: AppRuntime | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.extras.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.extras[key] = value
