"""比价爬取循环辅助函数测试。"""

from __future__ import annotations

from dingda_sidecar.agent.graph.crawl_loop import (
    dedupe_items,
    needs_more_crawl,
    route_after_analyze,
)


def test_dedupe_items_by_url() -> None:
    items = [
        {"url": "https://a/1", "title": "A"},
        {"url": "https://a/1", "title": "A dup"},
        {"title": "B only"},
        {"title": "B only"},
    ]
    out = dedupe_items(items)
    assert len(out) == 2
    assert out[0]["title"] == "A"
    assert out[1]["title"] == "B only"


def test_needs_more_crawl_when_items_sparse() -> None:
    state = {
        "crawl_round": 0,
        "continue_crawl": True,
        "xianyu_items": [{"title": "x"}],
        "alibaba_items": [],
        "matches": [],
    }
    assert needs_more_crawl(state) is True


def test_needs_more_crawl_stops_when_enough_matches() -> None:
    state = {
        "crawl_round": 1,
        "continue_crawl": True,
        "xianyu_items": [{"title": "a"}, {"title": "b"}],
        "alibaba_items": [{"title": "c"}, {"title": "d"}],
        "matches": [{"title_key": "a"}, {"title_key": "b"}],
    }
    assert needs_more_crawl(state) is False
    assert route_after_analyze(state) == "finalize"


def test_needs_more_crawl_respects_max_rounds() -> None:
    state = {
        "crawl_round": 3,
        "continue_crawl": True,
        "xianyu_items": [],
        "alibaba_items": [],
        "matches": [],
    }
    assert needs_more_crawl(state) is False


def test_needs_more_crawl_skipped_when_no_cookies() -> None:
    state = {
        "crawl_skipped": "未配置渠道账号 cookies",
        "crawl_round": 0,
        "xianyu_items": [],
        "alibaba_items": [],
        "matches": [],
    }
    assert needs_more_crawl(state) is False


def test_route_after_refine_when_ai_stops() -> None:
    from dingda_sidecar.agent.workflows.price_compare import _route_after_refine

    state = {"continue_crawl": False, "crawl_round": 1}
    assert _route_after_refine(state) == "finalize"
