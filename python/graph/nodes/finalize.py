"""finalize 节点 — 生成最终回复。"""

from __future__ import annotations

from graph.core.context import GraphContext
from graph.core.state import GraphState


def finalize_node(state: GraphState, ctx: GraphContext) -> dict[str, str]:
    query = state.get("query", "")
    plan = state.get("plan", "")
    analysis = state.get("analysis", "")
    reply = ctx.llm(
        f"用户需求：{query}\n计划：{plan}\n分析：{analysis}\n请给出最终回复。",
    )
    return {"reply": reply}
