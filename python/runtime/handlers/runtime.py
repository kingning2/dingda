"""Runtime 状态 IPC — 供 Rust lifecycle 轮询。

聚合 observability 快照（活跃编排、错误、WSS 摘要）返回给宿主。"""

from __future__ import annotations

from runtime.observability import get_runtime_observability


def build_runtime_status() -> dict:
    return get_runtime_observability().snapshot()
