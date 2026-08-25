"""比价工作流 — planner → search → normalize → match → analyze → finalize。"""

from __future__ import annotations

from typing import Any

from config.settings import AiSettings
from graph.core.config import GraphConfig
from graph.core.context import GraphContext
from graph.core.graph import bind_context
from graph.core.state import GraphState
from graph.nodes.analyze import analyze_node
from graph.nodes.finalize import finalize_node
from graph.nodes.match import match_node
from graph.nodes.normalize import normalize_node
from graph.nodes.planner import planner_node
from graph.nodes.search import search_node


def _compile_price_compare_graph(ctx: GraphContext) -> Any:
    from langgraph.graph import END, StateGraph

    graph = StateGraph(GraphState)
    graph.add_node("planner", bind_context(ctx, planner_node))
    graph.add_node("search", bind_context(ctx, _search_node_sync))
    graph.add_node("normalize", bind_context(ctx, normalize_node))
    graph.add_node("match", bind_context(ctx, match_node))
    graph.add_node("analyze", bind_context(ctx, analyze_node))
    graph.add_node("finalize", bind_context(ctx, finalize_node))

    graph.set_entry_point("planner")
    graph.add_edge("planner", "search")
    graph.add_edge("search", "normalize")
    graph.add_edge("normalize", "match")
    graph.add_edge("match", "analyze")
    graph.add_edge("analyze", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


def _search_node_sync(state: GraphState, ctx: GraphContext) -> dict[str, Any]:
    """LangGraph 同步节点内跑 async search。"""
    import asyncio

    coro = search_node(state, ctx)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    future = asyncio.run_coroutine_threadsafe(coro, loop)
    return future.result()


def run_price_compare(
    config: GraphConfig,
    user: str,
    *,
    xianyu_items: list[dict[str, Any]] | None = None,
    alibaba_items: list[dict[str, Any]] | None = None,
    ai_settings: AiSettings | None = None,
) -> str:
    if ai_settings is not None:
        config = GraphConfig.from_ai_settings(ai_settings, system=config.system)
    ctx = GraphContext(config)
    compiled = _compile_price_compare_graph(ctx)
    initial: GraphState = {
        "query": user,
        "plan": "",
        "web_context": "",
        "knowledge_context": "",
        "xianyu_items": xianyu_items or [],
        "alibaba_items": alibaba_items or [],
        "normalized_items": [],
        "matches": [],
        "analysis": "",
        "reply": "",
    }
    result = compiled.invoke(initial)
    return str(result.get("reply", ""))


def run_reply(base_url: str, api_key: str, model: str, system: str, user: str) -> str:
    config = GraphConfig(base_url=base_url, api_key=api_key, model=model, system=system)
    return run_price_compare(config, user)


def run_reply_with_settings(settings: AiSettings, user: str, *, system: str = "") -> str:
    config = GraphConfig.from_ai_settings(settings, system=system)
    return run_price_compare(config, user, ai_settings=settings)
