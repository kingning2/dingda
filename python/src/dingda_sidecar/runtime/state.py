"""宿主 Runtime 状态枚举。"""

from __future__ import annotations

from enum import StrEnum


class RuntimeState(StrEnum):
    STOPPED = "stopped"
    STARTING = "starting"
    READY = "ready"
    RUNNING = "running"
    STOPPING = "stopping"
