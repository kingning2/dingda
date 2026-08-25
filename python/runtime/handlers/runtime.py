"""Runtime 状态 IPC — 供 Rust lifecycle 轮询。"""

from __future__ import annotations

from runtime.observability import get_runtime_observability


def build_runtime_status() -> dict:
    return get_runtime_observability().snapshot()
