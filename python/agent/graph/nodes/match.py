"""⑥ match — 跨平台同款配对（核验前）。

读：``normalized_items``
写：``matches``
"""

from __future__ import annotations

from agent.graph.context import GraphContext
from agent.graph.state import GraphState
from services.product import match_products


def match_node(state: GraphState, ctx: GraphContext) -> dict[str, object]:
    """在归一化商品上做跨平台匹配。"""
    del ctx
    normalized = state.get("normalized_items") or []
    return {"matches": match_products(normalized)}
