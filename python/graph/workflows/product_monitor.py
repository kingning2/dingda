"""商品监控工作流 — planner → search → analyze → finalize。"""

from __future__ import annotations

from graph.core.config import GraphConfig
from graph.core.context import GraphContext
from graph.core.graph import bind_context
from graph.core.state import GraphState
from graph.nodes.analyze import analyze_node
from graph.nodes.finalize import finalize_node
from graph.nodes.planner import planner_node
from graph.workflows.price_compare import _search_node_sync


def run_product_monitor(config: GraphConfig, user: str) -> str:
    from langgraph.graph import END, StateGraph

    ctx = GraphContext(config)
    graph = StateGraph(GraphState)
    graph.add_node("planner", bind_context(ctx, planner_node))
    graph.add_node("search", bind_context(ctx, _search_node_sync))
    graph.add_node("analyze", bind_context(ctx, analyze_node))
    graph.add_node("finalize", bind_context(ctx, finalize_node))

    graph.set_entry_point("planner")
    graph.add_edge("planner", "search")
    graph.add_edge("search", "analyze")
    graph.add_edge("analyze", "finalize")
    graph.add_edge("finalize", END)

    compiled = graph.compile()
    initial: GraphState = {
        "query": user,
        "plan": "",
        "web_context": "",
        "knowledge_context": "",
        "xianyu_items": [],
        "alibaba_items": [],
        "normalized_items": [],
        "matches": [],
        "analysis": "",
        "reply": "",
    }
    result = compiled.invoke(initial)
    return str(result.get("reply", ""))
