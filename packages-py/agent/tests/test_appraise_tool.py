"""鉴定工具单测：详情预算、本商品不许出现在同款里、单条失败不连坐。

``search_items`` / ``fetch_detail`` 换成假实现（真的会开浏览器），只验证工具**怎么
取数、怎么收口**：同款的详情条数有没有被 ``details`` 卡住、本商品会不会被自己当成
同款拉第二遍、一条同款撞风控会不会把整次鉴定拖垮、本商品自己拉不到时是不是
``ok=False``。本仓库没有 pytest-asyncio，一律 ``sync 函数 + asyncio.run``。
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

from agent.tools import appraise as appraise_tool
from conftest import make_ctx

_TARGET_ID = "t"

_TARGET_DETAIL = {
    "item_id": _TARGET_ID,
    "title": "【清仓】露营折叠桌 全新包邮",
    "price": "10",
    "want_count": "200",
    "browse_count": "2000",
    "sold_state": "on_sale",
    "seller_nick": "我",
    "url": "https://example.com/item/t",
}


def _shell(item_id: str, *, price: str = "40") -> dict[str, Any]:
    return {
        "item_id": item_id,
        "title": f"同款 {item_id}",
        "url": f"https://example.com/item/{item_id}",
        "platform": "xianyu",
        "price": price,
        "seller_nick": f"卖家{item_id}",
    }


def _detail(item_id: str, *, price: str = "40", want: str = "5") -> dict[str, Any]:
    return {
        **_shell(item_id, price=price),
        "want_count": want,
        "browse_count": "50",
        "sold_state": "on_sale",
    }


def _fake_search(ids: list[str], seen_queries: list[str] | None = None):
    """按调用顺序回一批壳；登记的 ``seen_queries`` 会记下每次用的词。"""

    async def search(ctx: Any, platform: str, query: str, limit: int = 30) -> dict[str, Any]:
        if seen_queries is not None:
            seen_queries.append(query)
        return {
            "ok": True,
            "platform": platform,
            "items": [_shell(i, price=str(40 + index)) for index, i in enumerate(ids)],
        }

    return search


def _fake_detail(fail: set[str] | None = None):
    """按 item_id 回一条详情；``fail`` 里的 id 返风控失败。"""
    fail = fail or set()

    async def detail(
        ctx: Any,
        platform: str,
        item_id: str,
        xsec_token: str | None = None,
        url: str | None = None,
    ) -> dict[str, Any]:
        if item_id in fail:
            return {
                "ok": False,
                "platform": platform,
                "items": [],
                "error_code": "channel.risk",
                "message": "风控",
            }
        row = dict(_TARGET_DETAIL) if item_id == _TARGET_ID else _detail(item_id)
        return {"ok": True, "platform": platform, "items": [row]}

    return detail


def test_details_budget_caps_peer_fetches() -> None:
    """``details`` 是硬上限：同款搜到 6 条，也只给前 2 条补详情。"""
    fetched: list[str] = []

    async def fake_detail(
        ctx: Any,
        platform: str,
        item_id: str,
        xsec_token: str | None = None,
        url: str | None = None,
    ) -> dict[str, Any]:
        fetched.append(item_id)
        return {"ok": True, "platform": platform, "items": [dict(_TARGET_DETAIL) if item_id == _TARGET_ID else _detail(item_id)]}

    ctx = make_ctx()
    with patch.object(appraise_tool, "search_items", _fake_search(["a", "b", "c", "d", "e", "f"])), \
         patch.object(appraise_tool, "fetch_detail", fake_detail):
        out = asyncio.run(appraise_tool.appraise_item_tool(ctx, item_id=_TARGET_ID, details=2))

    assert out["ok"] is True
    peers = [item_id for item_id in fetched if item_id != _TARGET_ID]
    assert peers == ["a", "b"], fetched
    assert out["detail_size"] == 2


def test_target_is_not_one_of_its_own_comparables() -> None:
    """本商品自己也出现在搜索结果里时，不许被当成同款再拉一遍详情。

    它是鉴定的主语，已经被拉过一次了。不剔的话中位价被自己拉平、价差恒为 0 ——
    症状是「所有商品都判不值得」，一个不报错但全错的静默故障。
    """
    fetched: list[str] = []

    async def fake_detail(
        ctx: Any,
        platform: str,
        item_id: str,
        xsec_token: str | None = None,
        url: str | None = None,
    ) -> dict[str, Any]:
        fetched.append(item_id)
        return {"ok": True, "platform": platform, "items": [dict(_TARGET_DETAIL) if item_id == _TARGET_ID else _detail(item_id)]}

    ctx = make_ctx()
    with patch.object(appraise_tool, "search_items", _fake_search([_TARGET_ID, "a", "b", "c"])), \
         patch.object(appraise_tool, "fetch_detail", fake_detail):
        out = asyncio.run(appraise_tool.appraise_item_tool(ctx, item_id=_TARGET_ID, details=4))

    assert fetched.count(_TARGET_ID) == 1, fetched

    rows = out["comparables"]
    targets = [row for row in rows if row["is_target"]]
    assert len(targets) == 1
    assert targets[0]["item_id"] == _TARGET_ID
    # 同款表 = 3 条同款 + 本商品自己一行；本商品没有被重复算成一条同款。
    assert len(rows) == 4
    assert out["sample_size"] == 3


def test_one_peer_detail_failure_does_not_sink_the_run() -> None:
    """一条同款撞风控 → 进 ``issues``，它退化成只有价格的壳继续参与价格基线。"""
    ctx = make_ctx()
    with patch.object(appraise_tool, "search_items", _fake_search(["a", "b", "c"])), \
         patch.object(appraise_tool, "fetch_detail", _fake_detail(fail={"b"})):
        out = asyncio.run(appraise_tool.appraise_item_tool(ctx, item_id=_TARGET_ID, details=3))

    assert out["ok"] is True
    assert any(issue["error_code"] == "channel.risk" for issue in out["issues"])
    ids = [row["item_id"] for row in out["comparables"]]
    assert ids == ["a", "b", "c", _TARGET_ID] or set(ids) == {"a", "b", "c", _TARGET_ID}
    # 失败的那条仍在同款表里，只是没量到需求 —— 不该被悄悄抹掉。
    assert "b" in ids


def test_target_detail_failure_fails_the_whole_run() -> None:
    """本商品自己拉不到详情 → ``ok=False``，错误码原样透出来。

    它是鉴定的主语，缺了什么都算不出来；同款拉不到只是少一行旁证。
    """
    ctx = make_ctx()
    with patch.object(appraise_tool, "search_items", _fake_search(["a"])), \
         patch.object(appraise_tool, "fetch_detail", _fake_detail(fail={_TARGET_ID})):
        out = asyncio.run(appraise_tool.appraise_item_tool(ctx, item_id=_TARGET_ID))

    assert out["ok"] is False
    assert out["error_code"] == "channel.risk"
    assert out["target"] is None
    assert out["comparables"] == []


def test_empty_target_detail_fails_the_run() -> None:
    """详情 HTTP 成功但一条都没有 → ``crawler.empty``，不能拿空壳往下算。"""
    async def fake_detail(
        ctx: Any,
        platform: str,
        item_id: str,
        xsec_token: str | None = None,
        url: str | None = None,
    ) -> dict[str, Any]:
        return {"ok": True, "platform": platform, "items": [] if item_id == _TARGET_ID else [_detail(item_id)]}

    ctx = make_ctx()
    with patch.object(appraise_tool, "search_items", _fake_search(["a"])), \
         patch.object(appraise_tool, "fetch_detail", fake_detail):
        out = asyncio.run(appraise_tool.appraise_item_tool(ctx, item_id=_TARGET_ID))

    assert out["ok"] is False
    assert out["error_code"] == "crawler.empty"


def test_search_failure_fails_the_run_with_that_code() -> None:
    """搜索本身挂了（风控 / 空结果）是真失败，交回主编排按码分流。"""
    async def fake_search(ctx: Any, platform: str, query: str, limit: int = 30) -> dict[str, Any]:
        return {"ok": False, "platform": platform, "items": [], "error_code": "account.session_expired", "message": "登录失效"}

    ctx = make_ctx()
    with patch.object(appraise_tool, "search_items", fake_search), \
         patch.object(appraise_tool, "fetch_detail", _fake_detail()):
        out = asyncio.run(appraise_tool.appraise_item_tool(ctx, item_id=_TARGET_ID))

    assert out["ok"] is False
    assert out["error_code"] == "account.session_expired"


def test_url_only_input_resolves_the_id() -> None:
    """只给链接时从 ``?id=`` 与 ``/item/<id>`` 两种形状里取 id。"""
    assert appraise_tool.item_id_from_url("https://www.goofish.com/item?id=123456789") == "123456789"
    assert appraise_tool.item_id_from_url("https://www.goofish.com/item/987654321") == "987654321"
    # 取不到就返回空串 —— **不猜**：猜错的 id 会拉到一个不相干的商品。
    assert appraise_tool.item_id_from_url("https://www.goofish.com/some/page") == ""


def test_unresolvable_url_is_rejected() -> None:
    """链接认不出 id、又没给 item_id → ``agent.invalid_input``，让编排先去 crawl。"""
    ctx = make_ctx()
    out = asyncio.run(appraise_tool.appraise_item_tool(ctx, url="https://www.goofish.com/some/page"))
    assert out["ok"] is False
    assert out["error_code"] == "agent.invalid_input"


def test_missing_id_and_url_is_rejected() -> None:
    ctx = make_ctx()
    out = asyncio.run(appraise_tool.appraise_item_tool(ctx))
    assert out["ok"] is False
    assert out["error_code"] == "agent.invalid_input"


def test_unsupported_platform_is_rejected() -> None:
    """拼多多这种没接的平台直接拒掉，别让它变成一个空鉴定混进结论。"""
    ctx = make_ctx()
    out = asyncio.run(appraise_tool.appraise_item_tool(ctx, platform="pinduoduo", item_id=_TARGET_ID))
    assert out["ok"] is False
    assert out["error_code"] == "agent.invalid_input"


def test_query_falls_back_to_the_title_and_is_echoed() -> None:
    """没给检索词就从标题截；截出来的词必须回显 —— 用户要能追「同款是拿什么搜的」。"""
    seen: list[str] = []
    ctx = make_ctx()
    with patch.object(appraise_tool, "search_items", _fake_search(["a"], seen_queries=seen)), \
         patch.object(appraise_tool, "fetch_detail", _fake_detail()):
        out = asyncio.run(appraise_tool.appraise_item_tool(ctx, item_id=_TARGET_ID))

    # 标题「【清仓】露营折叠桌 全新包邮」→ 去括号段、去营销词。
    assert seen == ["露营折叠桌"]
    assert out["query"] == "露营折叠桌"


def test_explicit_query_wins_over_the_title() -> None:
    """显式传的检索词优先 —— 标题截得不好时主编排能纠正。"""
    seen: list[str] = []
    ctx = make_ctx()
    with patch.object(appraise_tool, "search_items", _fake_search(["a"], seen_queries=seen)), \
         patch.object(appraise_tool, "fetch_detail", _fake_detail()):
        out = asyncio.run(
            appraise_tool.appraise_item_tool(ctx, item_id=_TARGET_ID, query="野营桌")
        )

    assert seen == ["野营桌"]
    assert out["query"] == "野营桌"


def test_cancelled_run_stops_before_more_details() -> None:
    """取消信号置位后不再往下拉同款详情，标 ``partial`` 收尾。"""
    cancel = asyncio.Event()
    cancel.set()
    fetched: list[str] = []

    async def fake_detail(
        ctx: Any,
        platform: str,
        item_id: str,
        xsec_token: str | None = None,
        url: str | None = None,
    ) -> dict[str, Any]:
        fetched.append(item_id)
        return {"ok": True, "platform": platform, "items": [dict(_TARGET_DETAIL) if item_id == _TARGET_ID else _detail(item_id)]}

    ctx = make_ctx(cancel=cancel)
    with patch.object(appraise_tool, "search_items", _fake_search(["a", "b", "c"])), \
         patch.object(appraise_tool, "fetch_detail", fake_detail):
        out = asyncio.run(appraise_tool.appraise_item_tool(ctx, item_id=_TARGET_ID, details=3))

    assert out["ok"] is True
    assert out["partial"] is True
    assert fetched == [_TARGET_ID], fetched
    assert any(issue["error_code"] == "agent.cancelled" for issue in out["issues"])


def test_payload_does_not_look_like_a_product_list() -> None:
    """出参不许带顶层 ``platform`` + ``items``。

    前端 ``extractProducts`` 看到这两个键就会把结果吞进商品面板 —— 鉴定载荷会被
    当成商品列表渲染。所以平台放 ``target.platform``，同款数组叫 ``comparables``。
    """
    ctx = make_ctx()
    with patch.object(appraise_tool, "search_items", _fake_search(["a", "b", "c"])), \
         patch.object(appraise_tool, "fetch_detail", _fake_detail()):
        out = asyncio.run(appraise_tool.appraise_item_tool(ctx, item_id=_TARGET_ID, details=3))

    assert out["kind"] == "product_appraisal"
    assert "platform" not in out
    assert "items" not in out
    assert out["target"]["platform"] == "xianyu"
    assert out["verdict"] in {"worth", "caution", "skip", "insufficient"}


def test_input_caps_are_enforced_by_schema() -> None:
    """上限写在校验里，不写在提示词里 —— 模型多要也要不上去。"""
    import pydantic

    for bad in (9, -1):
        try:
            appraise_tool.AppraiseInput(item_id="t", details=bad)
        except pydantic.ValidationError:
            pass
        else:
            raise AssertionError(f"details={bad} 应当被拒")
