"""normalize 节点 — 商品字段归一化。

调用 ``services.product.normalize_products``，统一标题/价格等供匹配与分析使用。"""

from __future__ import annotations

from graph.core.context import GraphContext
from graph.core.state import GraphState
from services.product import normalize_products


def normalize_node(state: GraphState, ctx: GraphContext) -> dict[str, object]:
    del ctx
    xianyu = state.get("xianyu_items") or []
    alibaba = state.get("alibaba_items") or []
    return {"normalized_items": normalize_products(xianyu, alibaba)}
