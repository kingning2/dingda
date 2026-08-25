"""planner 节点。"""

from __future__ import annotations

from agents.planner import plan
from graph.core.context import GraphContext
from graph.core.state import GraphState


def planner_node(state: GraphState, ctx: GraphContext) -> dict[str, str]:
    return plan(state, ctx)
