"""⑧ finalize — 汇总调研计划与核验结论 → 用户回复。

读：``query``、``plan``、``keywords``、``analysis``
写：``reply``
"""

from __future__ import annotations

from dingda_sidecar.agent.graph.context import GraphContext
from dingda_sidecar.agent.graph.state import GraphState


def finalize_node(state: GraphState, ctx: GraphContext) -> dict[str, str]:
    """末节点：面向用户的可执行回复。"""
    query = state.get("query", "")
    plan = state.get("plan", "")
    keywords = state.get("keywords") or []
    analysis = state.get("analysis", "")
    kw = "、".join(str(k) for k in keywords) if keywords else "（无）"
    reply = ctx.llm(
        f"用户需求：{query}\n计划：{plan}\n核验关键词：{kw}\n"
        f"核验分析：{analysis}\n"
        "请给出最终回复（含：值得跟进的候选、是否已核验、建议下一步）。",
    )
    return {"reply": reply}
