"""Runtime 领域服务。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass(slots=True)
class RuntimeService:
    """记录进程启动时刻，并生成可序列化的状态快照。"""

    started_at: float = field(default_factory=time.monotonic)

    def snapshot(self, *, phase: str | None = None) -> dict[str, object]:
        uptime_ms = int((time.monotonic() - self.started_at) * 1000)
        payload: dict[str, object] = {
            "ok": True,
            "state": "running",
            "uptime_ms": uptime_ms,
        }
        if phase is not None:
            payload["phase"] = phase
        return payload
