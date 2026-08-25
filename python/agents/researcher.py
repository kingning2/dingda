"""调研 Agent — 汇总搜索结果与渠道上下文为分析前摘要。

在 analyze 节点中先于深度分析调用，把检索材料压成 GraphState.analysis。"""

from __future__ import annotations

from graph.core.context import GraphContext
from graph.core.state import GraphState


def research(state: GraphState, ctx: GraphContext) -> dict[str, str]:
    """整合 web 与渠道检索结果为调研摘要。"""
    query = state.get("query", "")
    plan = state.get("plan", "")
    web = state.get("web_context", "")
    xianyu_count = len(state.get("xianyu_items") or [])
    alibaba_count = len(state.get("alibaba_items") or [])

    prompt = (
        f"用户需求：{query}\n"
        f"计划：{plan}\n"
        f"网页检索：{web or '（无）'}\n"
        f"闲鱼结果数：{xianyu_count}，1688 结果数：{alibaba_count}\n"
        "请简要总结当前调研发现（3-5 句）。"
    )
    summary = ctx.llm(prompt)
    return {"analysis": summary}
