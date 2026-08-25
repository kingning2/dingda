"""LangGraph 共享状态。"""

from __future__ import annotations

from typing import Any, TypedDict


class GraphState(TypedDict, total=False):
    query: str
    plan: str
    web_context: str
    knowledge_context: str
    account_id: str
    cookies: list[dict[str, Any]]
    xianyu_items: list[dict[str, Any]]
    alibaba_items: list[dict[str, Any]]
    normalized_items: list[dict[str, Any]]
    matches: list[dict[str, Any]]
    analysis: str
    reply: str


class BuyerReplyState(TypedDict, total=False):
    user_message: str
    peer_name: str
    item_id: str
    item_title: str
    history: str
    bargain_count: int
    intent: str
    reply: str
    skip: bool
