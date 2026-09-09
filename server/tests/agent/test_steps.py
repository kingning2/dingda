"""steps 形状单测。"""

from __future__ import annotations

from src.agent.runtimes.steps import (
    normalize_tool_name,
    page_from_live_frame,
    step_for_tool_call,
    step_for_tool_result,
)


def test_preview_tool_is_browser_crawl() -> None:
    step = step_for_tool_call("c1", "preview", {"url": "https://example.com"})
    assert step["kind"] == "browser_crawl"
    assert step["page"]["url"] == "https://example.com"
    assert step["page"]["loading"] is True


def test_search_tool_is_browser_crawl_with_platform_label() -> None:
    step = step_for_tool_call(
        "c2",
        "dingda_search",
        {"platform": "xianyu", "query": "椅"},
    )
    assert step["kind"] == "browser_crawl"
    assert step["label"] == "search · 闲鱼"
    assert step["page"]["loading"] is True
    assert step["page"]["focus_label"] == "搜索「椅」"


def test_normalize_strips_mcp_prefix() -> None:
    assert normalize_tool_name("goofish_search") == "search"
    assert normalize_tool_name("dingda_product") == "product"
    assert normalize_tool_name("search") == "search"


def test_tool_result_ok_false_is_error() -> None:
    patch = step_for_tool_result(
        "c1",
        {"ok": False, "error_code": "account.session_expired", "message": "请扫码"},
        ok=True,
    )
    assert patch["status"]["state"] == "error"
    assert patch["hint"] == "请扫码"


def test_tool_result_and_page() -> None:
    patch = step_for_tool_result("c1", {"ok": True})
    assert patch["status"]["state"] == "ready"
    assert patch["page_loading"] is False
    page = page_from_live_frame(
        url="https://a",
        title="t",
        hint="直播中",
        screenshot_url="data:image/jpeg;base64,xx",
    )
    assert page["screenshot_url"].startswith("data:")
