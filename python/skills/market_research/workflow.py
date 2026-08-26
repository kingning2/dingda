"""比价工作流 — 先多篇调研，再计划+关键词，再爬虫核验。

入口（任选其一）::

    run_price_compare(config, user, ..., on_step=...)
    run_reply(...) / run_reply_with_settings(..., on_step=...)

节点顺序（每步会 ``ctx.step`` → 日志 + 可选回调）::

    web_research → article_analyze → planner → crawl
         → normalize → match → analyze → finalize → END

``on_step(name, status, *, index, total, label, detail)``：
status 为 ``running`` / ``done`` / ``error``；agent handler 用它更新
``track_workflow.stage``，Rust 经 ``/v1/runtime/status`` 的 ``active_ops`` 可见。
"""

from __future__ import annotations

from typing import Any

from agent.graph.builder import bind_context
from agent.graph.config import GraphConfig
from agent.graph.context import GraphContext, StepCallback
from agent.graph.nodes.analyze import analyze_node
from agent.graph.nodes.articles import article_analyze_node
from agent.graph.nodes.finalize import finalize_node
from agent.graph.nodes.match import match_node
from agent.graph.nodes.normalize import normalize_node
from agent.graph.nodes.planner import planner_node
from agent.graph.nodes.search import crawl_node, web_research_node
from agent.graph.state import GraphState
from config.settings import AiSettings

# 顺序即进度分母；改图时同步改这里
PRICE_COMPARE_STEPS: tuple[str, ...] = (
    "web_research",
    "article_analyze",
    "planner",
    "crawl",
    "normalize",
    "match",
    "analyze",
    "finalize",
)


def _compile_price_compare_graph(ctx: GraphContext) -> Any:
    """编译比价图：调研 → 计划 → 爬虫核验 → 成文。"""
    from langgraph.graph import END, StateGraph

    graph = StateGraph(GraphState)
    # 节点：各步职责（读/写字段见 agent.graph.state）；step= 用于进度上报
    graph.add_node(
        "web_research",
        bind_context(ctx, web_research_node, step="web_research"),
    )  # AI：web_fetch 检索 + web_scrape 抽正文
    graph.add_node(
        "article_analyze",
        bind_context(ctx, article_analyze_node, step="article_analyze"),
    )  # 多篇材料 → 利润候选结论
    graph.add_node(
        "planner",
        bind_context(ctx, planner_node, step="planner"),
    )  # 基于调研出计划 + keywords
    graph.add_node(
        "crawl",
        bind_context(ctx, _crawl_node_sync, step="crawl"),
    )  # 按关键词爬闲鱼/1688 核验
    graph.add_node(
        "normalize",
        bind_context(ctx, normalize_node, step="normalize"),
    )  # 两边商品字段对齐
    graph.add_node(
        "match",
        bind_context(ctx, match_node, step="match"),
    )  # 跨平台同款配对
    graph.add_node(
        "analyze",
        bind_context(ctx, analyze_node, step="analyze"),
    )  # 对照实盘核验文章说法
    graph.add_node(
        "finalize",
        bind_context(ctx, finalize_node, step="finalize"),
    )  # 汇总成面向用户的 reply

    graph.set_entry_point("web_research")  # 先上网，不先空想计划
    graph.add_edge("web_research", "article_analyze")  # 材料齐了再分析
    graph.add_edge("article_analyze", "planner")  # 有结论才出计划+关键词
    graph.add_edge("planner", "crawl")  # 关键词落地爬虫核验
    graph.add_edge("crawl", "normalize")  # 原始列表 → 统一 schema
    graph.add_edge("normalize", "match")  # 归一化后再配对
    graph.add_edge("match", "analyze")  # 配对结果进核验分析
    graph.add_edge("analyze", "finalize")  # 核验结论 → 最终文案
    graph.add_edge("finalize", END)
    return graph.compile()


def _crawl_node_sync(state: GraphState, ctx: GraphContext) -> dict[str, Any]:
    """同步壳：在 LangGraph 同步节点里跑 async ``crawl_node``。"""
    import asyncio

    coro = crawl_node(state, ctx)
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
    on_step: StepCallback | None = None,
) -> str:
    """跑完整比价流，返回 ``state["reply"]``。

    ``on_step``：每节点 running/done/error 时回调（见模块 docstring）。
    """
    if ai_settings is not None:
        config = GraphConfig.from_ai_settings(ai_settings, system=config.system)
    ctx = GraphContext(config, on_step=on_step, steps=PRICE_COMPARE_STEPS)
    compiled = _compile_price_compare_graph(ctx)
    initial: GraphState = {
        "query": user,
        "plan": "",
        "keywords": [],
        "web_context": "",
        "web_sources": [],
        "knowledge_context": "",
        "xianyu_items": xianyu_items or [],
        "alibaba_items": alibaba_items or [],
        "normalized_items": [],
        "matches": [],
        "analysis": "",
        "reply": "",
    }
    step_total = len(PRICE_COMPARE_STEPS)
    if on_step is not None:
        on_step(
            "price_compare",
            "running",
            index=0,
            total=step_total,
            label="0/8 start",
            detail=user[:80],
        )
    try:
        result = compiled.invoke(initial)
    except Exception:
        if on_step is not None:
            on_step(
                "price_compare",
                "error",
                index=0,
                total=step_total,
                label="failed",
                detail="",
            )
        raise
    if on_step is not None:
        on_step(
            "price_compare",
            "done",
            index=step_total,
            total=step_total,
            label="done",
            detail="",
        )
    return str(result.get("reply", ""))


def run_reply(
    base_url: str,
    api_key: str,
    model: str,
    system: str,
    user: str,
    *,
    on_step: StepCallback | None = None,
) -> str:
    """旧 agent IPC：裸连接参数 → 比价流。"""
    config = GraphConfig(base_url=base_url, api_key=api_key, model=model, system=system)
    return run_price_compare(config, user, on_step=on_step)


def run_reply_with_settings(
    settings: AiSettings,
    user: str,
    *,
    system: str = "",
    on_step: StepCallback | None = None,
) -> str:
    """新入口：AiSettings → 比价流（Rust 侧 failover 后调用）。"""
    config = GraphConfig.from_ai_settings(settings, system=system)
    return run_price_compare(config, user, ai_settings=settings, on_step=on_step)
