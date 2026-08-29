"""比价爬取循环 — 路由与去重辅助。"""

from __future__ import annotations

from typing import Any, Literal

from dingda_sidecar.agent.graph.state import GraphState

MAX_CRAWL_ROUNDS = 3
MIN_MATCHES_TO_STOP = 2
MIN_ITEMS_PER_PLATFORM = 2
KEYWORDS_PER_ROUND = 5


def dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按 url / title 去重，保留先出现的条目。"""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        key = str(
            item.get("url")
            or item.get("item_url")
            or item.get("link")
            or item.get("title")
            or item.get("name")
            or ""
        ).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def needs_more_crawl(state: GraphState) -> bool:
    """analyze 之后：数据不足且未达轮次上限则继续爬。"""
    if state.get("crawl_skipped"):
        return False
    crawl_round = int(state.get("crawl_round") or 0)
    if crawl_round >= MAX_CRAWL_ROUNDS:
        return False
    if state.get("continue_crawl") is False:
        return False

    matches = len(state.get("matches") or [])
    if matches >= MIN_MATCHES_TO_STOP:
        return False

    xy = len(state.get("xianyu_items") or [])
    ab = len(state.get("alibaba_items") or [])
    if xy < MIN_ITEMS_PER_PLATFORM or ab < MIN_ITEMS_PER_PLATFORM:
        return True
    return matches < 1


def route_after_analyze(state: GraphState) -> Literal["refine", "finalize"]:
    return "refine" if needs_more_crawl(state) else "finalize"
