"""match 节点 — 跨平台商品匹配。

调用 ``services.product.match_products``，把归一化商品配对写入 GraphState.matches。"""

from __future__ import annotations

from graph.core.context import GraphContext
from graph.core.state import GraphState
from services.product import match_products


def match_node(state: GraphState, ctx: GraphContext) -> dict[str, object]:
    del ctx
    normalized = state.get("normalized_items") or []
    return {"matches": match_products(normalized)}
