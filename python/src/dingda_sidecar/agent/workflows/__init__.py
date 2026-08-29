"""工作流定义包 — 延迟导出编排入口。

- ``run_price_compare`` / ``run_reply`` → 比价图（``price_compare``）
- ``run_buyer_reply`` → 买家回复 guard/generate 条件图
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "PRICE_COMPARE_STEPS",
    "run_buyer_reply",
    "run_price_compare",
    "run_reply",
    "run_reply_with_settings",
]


def __getattr__(name: str) -> Any:
    if name in {
        "PRICE_COMPARE_STEPS",
        "run_price_compare",
        "run_reply",
        "run_reply_with_settings",
    }:
        from dingda_sidecar.agent.workflows import price_compare

        return getattr(price_compare, name)
    if name == "run_buyer_reply":
        from dingda_sidecar.agent.workflows.buyer_reply import run_buyer_reply

        return run_buyer_reply
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
