"""⑤ normalize — 两边商品字段对齐（爬虫之后）。

读：``xianyu_items``、``alibaba_items``
写：``normalized_items``
"""

from __future__ import annotations

from dingda_sidecar.agent.graph.context import GraphContext
from dingda_sidecar.agent.graph.state import GraphState
from dingda_sidecar.services.product import normalize_products


def normalize_node(state: GraphState, ctx: GraphContext) -> dict[str, object]:
    """把闲鱼/1688 原始列表归一成同一结构。"""
    del ctx
    xianyu = state.get("xianyu_items") or []
    alibaba = state.get("alibaba_items") or []
    return {"normalized_items": normalize_products(xianyu, alibaba)}
