"""⑦ analyze — 爬虫核验后的结论（业务写在本节点）。

读：plan / keywords / 先前 analysis / 渠道列表 / matches
写：``analysis``
"""

from __future__ import annotations

from agent.graph.context import GraphContext
from agent.graph.state import GraphState


def analyze_node(state: GraphState, ctx: GraphContext) -> dict[str, str]:
    """用渠道实盘数据核验「高利润」说法。"""
    query = state.get("query", "")
    plan = state.get("plan", "")
    prior = state.get("analysis", "")
    keywords = state.get("keywords") or []
    matches = state.get("matches") or []
    normalized = state.get("normalized_items") or []
    xianyu_n = len(state.get("xianyu_items") or [])
    alibaba_n = len(state.get("alibaba_items") or [])
    prompt = (
        f"用户品类：{query}\n"
        f"计划：{plan}\n"
        f"爬虫关键词：{', '.join(str(k) for k in keywords) or '（无）'}\n"
        f"此前文章分析：{prior}\n"
        f"闲鱼条数：{xianyu_n}，1688 条数：{alibaba_n}，"
        f"归一化：{len(normalized)}，跨平台匹配对：{len(matches)}\n"
        "请核验：网上说的高利润候选，在爬虫结果里是否站得住脚；"
        "有匹配则点出差价线索，无数据则明确说「未能核验」并建议下一步。"
    )
    return {"analysis": ctx.llm(prompt)}
