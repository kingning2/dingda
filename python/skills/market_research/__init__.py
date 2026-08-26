"""选品 / 市场调研技能。"""

from __future__ import annotations

from typing import Any

from skills.market_research.skill import (
    RESEARCH_TOOL_NAMES,
    SKILL_ID,
    SPEC,
    TOOL_NAMES,
    MarketResearchParams,
    research_tools,
)

__all__ = [
    "MarketResearchParams",
    "PRICE_COMPARE_STEPS",
    "RESEARCH_TOOL_NAMES",
    "SKILL_ID",
    "SPEC",
    "TOOL_NAMES",
    "research_tools",
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
        from skills.market_research import workflow

        return getattr(workflow, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
