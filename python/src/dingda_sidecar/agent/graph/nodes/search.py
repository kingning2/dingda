"""① web_research / ④ crawl — 网页调研与关键词爬虫核验。

- ``web_research_node``：AI 调 ``web_fetch`` 检索 + ``web_scrape`` 抽正文
  → ``web_context`` / ``web_sources``
- ``crawl_node``：按 ``keywords`` 抓闲鱼/1688，核实计划是否靠谱（async）
"""

from __future__ import annotations

import logging
from typing import Any

from dingda_sidecar.agent.graph.context import GraphContext
from dingda_sidecar.agent.graph.crawl_loop import KEYWORDS_PER_ROUND, dedupe_items
from dingda_sidecar.agent.graph.state import GraphState
from dingda_sidecar.agent.llm.tool_loop import run_tool_loop
from dingda_sidecar.tools.alibaba import search_alibaba
from dingda_sidecar.tools.knowledge import retrieve_knowledge
from dingda_sidecar.tools.registry import format_tools_for_ai
from dingda_sidecar.tools.web.bindings import (
    format_web_context,
    make_web_fetch_tool,
    make_web_research_tools,
    sources_from_tool_payloads,
)
from dingda_sidecar.tools.xianyu import search_xianyu

logger = logging.getLogger("dingda.graph.web_research")

_WEB_TOOL_NAMES = ("web_fetch", "web_scrape")


def _research_system() -> str:
    return "\n".join(
        [
            format_tools_for_ai(_WEB_TOOL_NAMES),
            "",
            "执行要求：先 web_fetch（可加 site:域名），再对相关 URL 调用 web_scrape；",
            "禁止编造标题、链接或正文；没调用工具就不要声称看过网页。",
            "材料够用后用中文简短说明搜到了什么即可。",
        ]
    )


def web_research_node(state: GraphState, ctx: GraphContext) -> dict[str, Any]:
    """AI：web_fetch 选源 → web_scrape 抽正文 → 下游再读 materials。"""
    query = (state.get("query") or "").strip()
    if not query:
        return {"web_context": "", "knowledge_context": "", "web_sources": []}

    tools = make_web_research_tools()
    payloads: list[str] = []

    def _on_tool(name: str, args: dict[str, Any], payload: str) -> None:
        if name in _WEB_TOOL_NAMES:
            payloads.append(payload)
            preview = {
                k: (str(v)[:120] if not isinstance(v, (int, float)) else v) for k, v in args.items()
            }
            logger.info("web_research.tool name=%s args=%s", name, preview)

    note, _messages = run_tool_loop(
        ctx.model,
        tools,
        system=_research_system(),
        user=(f"用户选品需求：{query}\n请先 web_fetch，再对关键链接 web_scrape 完成调研。"),
        max_rounds=6,
        on_tool=_on_tool,
    )
    sources = sources_from_tool_payloads(payloads)
    # ponytail: 拒 tool / 空结果时兜一次 fetch
    if not sources:
        logger.warning("web_research.fallback_direct_fetch query=%s", query[:120])
        fetch = make_web_fetch_tool()
        payloads.append(fetch.invoke({"query": query, "max_results": 6}))
        sources = sources_from_tool_payloads(payloads)

    web_context = format_web_context(sources, note=note)
    logger.info(
        "web_research.done sources=%s urls=%s note_chars=%s",
        len(sources),
        [s.get("url") for s in sources if s.get("url")][:10],
        len(note or ""),
    )
    return {
        "web_context": web_context,
        "knowledge_context": retrieve_knowledge(query),
        "web_sources": sources,
    }


async def crawl_node(state: GraphState, ctx: GraphContext) -> dict[str, Any]:
    """计划落地后：用 keywords 爬渠道，核验网上说的利润品是否真实存在。"""
    keywords = [str(k).strip() for k in (state.get("keywords") or []) if str(k).strip()]
    if not keywords:
        q = (state.get("query") or "").strip()
        keywords = [q] if q else []
    keywords = keywords[:KEYWORDS_PER_ROUND]

    account_id = str(state.get("account_id") or "").strip()
    cookies = state.get("cookies")
    if not keywords:
        return {}
    if not (account_id and isinstance(cookies, list)):
        logger.warning(
            "crawl.skip missing account_id=%s cookies=%s keywords=%s",
            account_id or "-",
            len(cookies) if isinstance(cookies, list) else 0,
            keywords,
        )
        return {"crawl_skipped": "未配置渠道账号 cookies，已跳过闲鱼/1688 采集"}

    existing_xy = list(state.get("xianyu_items") or [])
    existing_ab = list(state.get("alibaba_items") or [])
    used = {str(k).strip() for k in (state.get("keywords_used") or []) if str(k).strip()}
    used.update(kw for kw in keywords)

    xianyu_all: list[dict[str, Any]] = []
    alibaba_all: list[dict[str, Any]] = []
    for kw in keywords:
        try:
            xianyu = await search_xianyu(
                kw,
                account_id=account_id,
                cookies=cookies,
                max_results=ctx.config.max_search_results,
            )
            xianyu_all.extend(xianyu.get("offers") or xianyu.get("items") or [])
        except Exception:
            pass
        try:
            alibaba = await search_alibaba(
                kw,
                account_id=account_id,
                cookies=cookies,
                max_results=ctx.config.max_search_results,
            )
            alibaba_all.extend(alibaba.get("offers") or alibaba.get("items") or [])
        except Exception:
            pass

    merged_xy = dedupe_items(existing_xy + xianyu_all)
    merged_ab = dedupe_items(existing_ab + alibaba_all)
    logger.info(
        "crawl.done round=%s keywords=%s xianyu=%s alibaba=%s",
        int(state.get("crawl_round") or 0),
        keywords,
        len(merged_xy),
        len(merged_ab),
    )
    return {
        "xianyu_items": merged_xy,
        "alibaba_items": merged_ab,
        "keywords_used": sorted(used),
    }
