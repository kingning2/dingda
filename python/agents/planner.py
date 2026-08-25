"""规划 Agent — 生成执行计划。"""

from __future__ import annotations

from graph.core.context import GraphContext
from graph.core.state import GraphState


def plan(state: GraphState, ctx: GraphContext) -> dict[str, str]:
    """根据用户 query 生成 1–3 步计划。"""
    query = state.get("query", "")
    plan_text = ctx.llm(f"请先给出执行计划（1-3 步）。用户需求：{query}")
    return {"plan": plan_text}
