"""match 节点。"""

from __future__ import annotations

from graph.core.context import GraphContext
from graph.core.state import GraphState
from services.product import match_products


def match_node(state: GraphState, ctx: GraphContext) -> dict[str, object]:
    del ctx
    normalized = state.get("normalized_items") or []
    return {"matches": match_products(normalized)}
