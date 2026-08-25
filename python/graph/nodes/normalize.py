"""normalize 节点。"""

from __future__ import annotations

from graph.core.context import GraphContext
from graph.core.state import GraphState
from services.product import normalize_products


def normalize_node(state: GraphState, ctx: GraphContext) -> dict[str, object]:
    del ctx
    xianyu = state.get("xianyu_items") or []
    alibaba = state.get("alibaba_items") or []
    return {"normalized_items": normalize_products(xianyu, alibaba)}
