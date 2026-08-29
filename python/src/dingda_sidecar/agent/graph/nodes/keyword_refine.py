"""keyword_refine — 爬取不足时由 AI 补充关键词，驱动下一轮 crawl。

读：``query`` / ``plan`` / ``analysis`` / ``keywords_used`` / 渠道与匹配统计
写：``keywords``、``keywords_used``、``crawl_round``、``continue_crawl``
"""

from __future__ import annotations

import re

from dingda_sidecar.agent.graph.context import GraphContext
from dingda_sidecar.agent.graph.crawl_loop import KEYWORDS_PER_ROUND, MAX_CRAWL_ROUNDS
from dingda_sidecar.agent.graph.state import GraphState

_KEYWORDS_LINE = re.compile(r"(?i)^\s*KEYWORDS\s*:\s*(.+)$")
_SUFFICIENT_LINE = re.compile(r"(?i)^\s*SUFFICIENT\s*:\s*(yes|true|是)\s*$")


def _parse_keywords(text: str) -> list[str]:
    for line in reversed(text.splitlines()):
        if _SUFFICIENT_LINE.match(line.strip()):
            return []
        m = _KEYWORDS_LINE.match(line.strip())
        if not m:
            continue
        parts = re.split(r"[,|，、/]+", m.group(1))
        return [p.strip() for p in parts if p.strip()][:KEYWORDS_PER_ROUND]
    return []


def keyword_refine_node(state: GraphState, ctx: GraphContext) -> dict[str, object]:
    """根据首轮/前轮核验结果，生成下一批可搜关键词。"""
    crawl_round = int(state.get("crawl_round") or 0) + 1
    used = {str(k).strip() for k in (state.get("keywords_used") or []) if str(k).strip()}
    for k in state.get("keywords") or []:
        ks = str(k).strip()
        if ks:
            used.add(ks)

    query = state.get("query", "")
    plan = state.get("plan", "")
    analysis = state.get("analysis", "")
    matches = state.get("matches") or []
    xy = len(state.get("xianyu_items") or [])
    ab = len(state.get("alibaba_items") or [])
    used_line = "、".join(sorted(used)) or "（无）"

    text = ctx.llm(
        "你在做选品比价的第二轮关键词补充。\n"
        f"用户品类/需求：{query}\n"
        f"执行计划：{plan}\n"
        f"已用关键词：{used_line}\n"
        f"当前核验分析：{analysis}\n"
        f"爬取统计：闲鱼 {xy} 条，1688 {ab} 条，跨平台匹配 {len(matches)} 组\n"
        f"当前为第 {crawl_round}/{MAX_CRAWL_ROUNDS} 轮补充。\n"
        "请判断：\n"
        "- 若数据已够核验，最后一行输出：SUFFICIENT: yes\n"
        "- 若需继续爬，最后一行输出：KEYWORDS: 词1 | 词2 | 词3\n"
        "新关键词必须具体可搜（商品名/型号），且不要重复已用关键词。",
    )

    new_keywords = [k for k in _parse_keywords(text) if k not in used]
    if not new_keywords:
        return {
            "crawl_round": crawl_round,
            "keywords_used": sorted(used),
            "continue_crawl": False,
        }

    return {
        "crawl_round": crawl_round,
        "keywords": new_keywords,
        "keywords_used": sorted(used),
        "continue_crawl": True,
    }
