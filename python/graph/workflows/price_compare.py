"""比价工作流 — planner → search → normalize → match → analyze → finalize。

LangGraph 线性编排，数据经 GraphState 逐节点流转：

1. ``planner``   — LLM 把用户查询拆成结构化搜索计划（关键词、平台、预算）。
2. ``search``    — 并行抓取闲鱼 + 1688 商品列表，写入 ``xianyu_items`` / ``alibaba_items``。
3. ``normalize`` — 两边字段对齐归一成 ``normalized_items``（标题/价格/成色等统一 schema）。
4. ``match``     — 跨平台同款配对，产出 ``matches``。
5. ``analyze``   — LLM 基于配对结果做比价分析，写 ``analysis``。
6. ``finalize``  — 汇总成面向用户的自然语言回复 ``reply``。

入口：``run_price_compare``（可注入已抓取的商品数据）、``run_reply`` /
``run_reply_with_settings``（兼容旧 agent IPC 直接传连接参数的调用方式）。
注意：商品监控工作流已移除——监控的 AI 决策由 Rust 侧
``feat/xianyu/monitor/ai.rs`` 经 ``/v1/agent/complete`` 单次补全完成，
不走本编排。"""

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
    """编译比价图：六个节点线性串联，无分支 / 无循环。

    节点函数经 ``bind_context`` 闭包注入 ``ctx``（LLM 客户端与配置），
    LangGraph 只看到 ``state -> partial state`` 的同步签名。
    每次调用重新编译（图本身无状态，编译成本低，避免跨请求共享可变上下文）。
    """
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
    """LangGraph 同步节点内跑 async search。

    search_node 是 async（Playwright 抓取），而 LangGraph 节点必须是同步函数。
    两种运行环境分别处理：
    - 无事件循环（sidecar handler 同步调用）：直接 ``asyncio.run``。
    - 已有事件循环（如嵌套在 async 服务里）：把协程投回原循环阻塞等待，
      避免在循环线程内二次 ``asyncio.run`` 报错。
    """
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
    """跑一次完整比价流，返回最终回复文本。

    ``xianyu_items`` / ``alibaba_items`` 可注入外部已抓取的商品数据，
    注入后 search 节点仍会执行但通常直接透传（由节点内部按非空跳过抓取）。
    """
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
    """旧 agent IPC 入口：直接传连接参数跑比价流。"""
    config = GraphConfig(base_url=base_url, api_key=api_key, model=model, system=system)
    return run_price_compare(config, user)


def run_reply_with_settings(settings: AiSettings, user: str, *, system: str = "") -> str:
    """新入口：从 AiSettings 构建配置跑比价流（Rust 侧 failover 后调用）。"""
    config = GraphConfig.from_ai_settings(settings, system=system)
    return run_price_compare(config, user, ai_settings=settings)
