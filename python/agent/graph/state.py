"""LangGraph 共享状态 TypedDict。

比价流（GraphState）与买家回复流（BuyerReplyState）各自独立，不要混用。

比价数据流（先调研，再计划，再爬虫核验）::

    入口          web_research     article_analyze    planner
    ────          ────────────     ───────────────    ───────
    query ──────► 读（多查询）      读                 读
                  写 web_context ─► 读 → 写 analysis ─► 读
                  写 knowledge_…                      写 plan
                                                      写 keywords
                                                           │
         crawl ◄───────────────────────────────────────────┘
         按 keywords 抓闲鱼/1688 → xianyu_items / alibaba_items
              │
         normalize → match → analyze（对照调研核验）→ finalize → reply
"""

from __future__ import annotations

from typing import Any, TypedDict


class GraphState(TypedDict, total=False):
    """比价编排通道。节点只返回要合并的 partial dict，未返回的字段原样保留。"""

    # ── 入口 / 规划 ──────────────────────────────────────────────
    query: str  # 用户原始需求（可为大类，如「百货」）
    plan: str  # 基于多篇调研后的执行计划；planner 写
    keywords: list[str]  # 计划拆出的爬虫关键词；planner 写，crawl 读

    # ── 网页调研（web_research 写）──────────────────────────────
    web_context: str  # 多查询拼成的「多篇材料」摘要
    web_sources: list[dict[str, Any]]  # 结构化来源：title/url/snippet/image
    knowledge_context: str  # 知识库；MVP 常空
    account_id: str  # 可选：有值才抓闲鱼/1688
    cookies: list[dict[str, Any]]  # 可选：配合 account_id

    # ── 商品管道（crawl 写列表）──────────────────────────────────
    xianyu_items: list[dict[str, Any]]
    alibaba_items: list[dict[str, Any]]
    normalized_items: list[dict[str, Any]]  # normalize 写
    matches: list[dict[str, Any]]  # match 写

    # ── 分析与回复 ───────────────────────────────────────────────
    analysis: str  # 先文章结论，后核验结论；article_analyze / analyze 写
    reply: str  # finalize 写


class BuyerReplyState(TypedDict, total=False):
    """买家 IM 自动回复通道（WSS auto_reply）。

    流程：guard（规则短路）→ 条件边 → generate（LLM）或 END。
    """

    user_message: str
    peer_name: str
    item_id: str
    item_title: str
    history: str
    bargain_count: int
    intent: str
    reply: str
    skip: bool
