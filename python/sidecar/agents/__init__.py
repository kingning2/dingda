"""LangGraph agent 模块 — 兼容层，委托 graph 工作流。

保留旧 import 路径，经 ``__getattr__`` 转发到新包，避免破坏调用方。"""

from __future__ import annotations

from typing import Any

__all__ = ["run_reply"]


def __getattr__(name: str) -> Any:
    if name == "run_reply":
        from graph.workflows.price_compare import run_reply

        return run_reply
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
