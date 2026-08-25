"""Agent 角色包 — 规划、调研、分析。

包级不做 eager import，避免 ``graph`` ↔ ``agents.analyst`` 循环依赖；
``analyze`` / ``plan`` / ``research`` 经 ``__getattr__`` 延迟加载。"""

from __future__ import annotations

from typing import Any

__all__ = ["analyze", "plan", "research"]


def __getattr__(name: str) -> Any:
    if name == "analyze":
        from agents.analyst import analyze

        return analyze
    if name == "plan":
        from agents.planner import plan

        return plan
    if name == "research":
        from agents.researcher import research

        return research
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
