"""分析 Agent — 比价与结论。"""

from __future__ import annotations

from graph.core.context import GraphContext
from graph.core.state import GraphState


def analyze(state: GraphState, ctx: GraphContext) -> dict[str, str]:
    """基于归一化商品与匹配结果给出分析。"""
    query = state.get("query", "")
    plan = state.get("plan", "")
    analysis = state.get("analysis", "")
    matches = state.get("matches") or []
    normalized = state.get("normalized_items") or []

    prompt = (
        f"用户需求：{query}\n"
        f"计划：{plan}\n"
        f"调研摘要：{analysis}\n"
        f"归一化商品数：{len(normalized)}，匹配对数：{len(matches)}\n"
        "请给出比价/选购分析结论（简洁、可执行）。"
    )
    result = ctx.llm(prompt)
    return {"analysis": result}
