"""③ planner — 调研之后出计划 + 爬虫关键词（业务写在本节点）。

读：``query``、``analysis``
写：``plan``、``keywords``
"""

from __future__ import annotations

import re

from agent.graph.context import GraphContext
from agent.graph.state import GraphState

_KEYWORDS_LINE = re.compile(r"(?i)^\s*KEYWORDS\s*:\s*(.+)$")


def _parse_keywords(plan_text: str) -> list[str]:
    for line in reversed(plan_text.splitlines()):
        m = _KEYWORDS_LINE.match(line.strip())
        if not m:
            continue
        parts = re.split(r"[,|，、/]+", m.group(1))
        return [p.strip() for p in parts if p.strip()][:5]
    return []


def planner_node(state: GraphState, ctx: GraphContext) -> dict[str, object]:
    """基于多篇分析写计划，并拆出具体可搜关键词。"""
    query = state.get("query", "")
    analysis = state.get("analysis", "")
    plan_text = ctx.llm(
        "你在做选品调研后的执行规划。\n"
        f"用户品类/需求：{query}\n"
        f"多篇材料分析结论：{analysis or '（无）'}\n"
        "请输出：\n"
        "1) 执行计划（1-3 步，说明要核验哪些高利润候选）\n"
        "2) 最后一行必须严格为：KEYWORDS: 词1 | 词2 | 词3\n"
        "关键词要具体可搜（商品名/型号），不要只写大类。",
    )
    keywords = _parse_keywords(plan_text)
    if not keywords and query.strip():
        keywords = [query.strip()]
    return {"plan": plan_text, "keywords": keywords}
