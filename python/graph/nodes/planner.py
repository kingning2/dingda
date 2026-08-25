"""planner 节点 — 委托规划 Agent 生成执行计划。

把 ``agents.planner.plan`` 结果写入 GraphState.plan。"""

from __future__ import annotations

from agents.planner import plan
from graph.core.context import GraphContext
from graph.core.state import GraphState


def planner_node(state: GraphState, ctx: GraphContext) -> dict[str, str]:
    return plan(state, ctx)
