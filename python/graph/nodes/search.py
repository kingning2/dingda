"""search 节点 — 网页检索 + 可选渠道工具。"""

from __future__ import annotations

from typing import Any

from graph.core.context import GraphContext
from graph.core.state import GraphState
from graph.tools.alibaba import search_alibaba
from graph.tools.knowledge import retrieve_knowledge
from graph.tools.xianyu import search_xianyu
from tools.web_search import web_search


async def search_node(state: GraphState, ctx: GraphContext) -> dict[str, Any]:
    query = state.get("query", "")
    result = web_search(query, max_results=ctx.config.max_search_results)
    knowledge = retrieve_knowledge(query)

    updates: dict[str, Any] = {
        "web_context": result,
        "knowledge_context": knowledge,
    }

    account_id = str(state.get("account_id") or "").strip()
    cookies = state.get("cookies")
    if account_id and isinstance(cookies, list) and query.strip():
        try:
            xianyu = await search_xianyu(
                query,
                account_id=account_id,
                cookies=cookies,
                max_results=ctx.config.max_search_results,
            )
            updates["xianyu_items"] = xianyu.get("offers") or xianyu.get("items") or []
        except Exception:
            updates["xianyu_items"] = state.get("xianyu_items") or []
        try:
            alibaba = await search_alibaba(
                query,
                account_id=account_id,
                cookies=cookies,
                max_results=ctx.config.max_search_results,
            )
            updates["alibaba_items"] = alibaba.get("offers") or alibaba.get("items") or []
        except Exception:
            updates["alibaba_items"] = state.get("alibaba_items") or []

    return updates
