"""analyze 节点。"""

from __future__ import annotations

from agents.analyst import analyze
from agents.researcher import research
from graph.core.context import GraphContext
from graph.core.state import GraphState


def analyze_node(state: GraphState, ctx: GraphContext) -> dict[str, str]:
    """先调研摘要，再深度分析。"""
    merged: GraphState = {**state, **research(state, ctx)}
    return analyze(merged, ctx)
