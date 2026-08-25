"""LangGraph 编排 — 节点、工具、工作流。"""

from __future__ import annotations

from typing import Any

__all__ = ["run_buyer_reply", "run_price_compare", "run_product_monitor", "run_reply"]


def __getattr__(name: str) -> Any:
    if name == "run_reply":
        from graph.workflows.price_compare import run_reply

        return run_reply
    if name == "run_price_compare":
        from graph.workflows.price_compare import run_price_compare

        return run_price_compare
    if name == "run_product_monitor":
        from graph.workflows.product_monitor import run_product_monitor

        return run_product_monitor
    if name == "run_buyer_reply":
        from graph.workflows.buyer_reply import run_buyer_reply

        return run_buyer_reply
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
