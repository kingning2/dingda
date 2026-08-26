"""工作流定义包 — 延迟导出编排入口。

- ``run_price_compare`` / ``run_reply`` → 比价图（调研→计划→爬虫核验）
- ``run_buyer_reply`` → 买家回复 guard/generate 条件图
"""

from __future__ import annotations

from typing import Any

__all__ = ["run_buyer_reply", "run_price_compare", "run_reply"]


def __getattr__(name: str) -> Any:
    if name == "run_reply":
        from skills.market_research.workflow import run_reply

        return run_reply
    if name == "run_price_compare":
        from skills.market_research.workflow import run_price_compare

        return run_price_compare
    if name == "run_buyer_reply":
        from agent.workflows.buyer_reply import run_buyer_reply

        return run_buyer_reply
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
