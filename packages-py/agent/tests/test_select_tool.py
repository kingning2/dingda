"""选品工具单测：上限、单候选失败不连坐、全失败取主因码。

``search_items`` / ``fetch_detail`` 换成假实现（真的会开浏览器），只验证工具**怎么
取数、怎么收口**：条数上限卡没卡住、一个候选撞风控会不会把别的候选也拖下水、
全灭时 ``ok=False`` 带的是不是主因码。本仓库没有 pytest-asyncio，一律
``sync 函数 + asyncio.run``。
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

from agent.tools import select as select_tool
from conftest import make_ctx


def _shell(item_id: str, *, price: str = "30") -> dict[str, Any]:
    return {
        "item_id": item_id,
        "title": f"货 {item_id}",
        "url": f"https://example.com/{item_id}",
        "platform": "xianyu",
        "price": price,
    }


def _detail(item_id: str, *, want: str = "100") -> dict[str, Any]:
    return {
        **_shell(item_id),
        "want_count": want,
        "browse_count": "500",
        "sold_state": "sold",
        "seller_nick": f"卖家{item_id}",
    }


def _fake_search(pages: dict[str, list[str]]):
    """按关键词回一批壳；没登记的关键词返空。"""

    async def search(ctx: Any, platform: str, query: str, limit: int = 30) -> dict[str, Any]:
        ids = pages.get(query, [])
        return {"ok": True, "platform": platform, "items": [_shell(i, price=str(10 + index)) for index, i in enumerate(ids)]}

    return search


def test_details_per_keyword_caps_the_fetch_count() -> None:
    """``details_per_keyword`` 与 ``keywords`` 的上限是乘起来的硬上限。"""
    fetched: list[str] = []

    async def fake_detail(ctx: Any, platform: str, item_id: str, **kwargs: Any) -> dict[str, Any]:
        fetched.append(item_id)
        return {"ok": True, "platform": platform, "items": [_detail(item_id)]}

    ctx = make_ctx()
    with patch.object(select_tool, "search_items", _fake_search({"甲": ["a1", "a2", "a3", "a4"], "乙": ["b1", "b2", "b3"]})), \
         patch.object(select_tool, "fetch_detail", fake_detail):
        out = asyncio.run(
            select_tool.select_products(ctx, keywords=["甲", "乙"], details_per_keyword=2)
        )

    assert out["ok"] is True
    assert len(fetched) == 4, fetched
    # 轮次分发：一轮每个候选各一条。顺序本身是契约的一部分 —— 见下一条测试为什么。
    assert fetched == ["a1", "b1", "a2", "b2"]


def test_every_candidate_gets_a_detail_before_any_gets_a_second() -> None:
    """【回归】详情按轮次发，不按候选顺序发。

    曾经是「一个候选的两条详情拉完再轮到下一个」。实测里 3 个候选只有第 1 个够到分，
    另外两个因超预算缺席 —— `demand`（要 ≥2 个候选量过需求）与 `entry`（要 ≥2 个不同
    价格）两个维度双双被剔，最后给用户一个 7.5 分、覆盖率 30% 的单候选「结论」，
    候选之间根本没得比。3 个候选各一条详情，至少让它们能比。
    """
    fetched: list[str] = []

    async def fake_detail(ctx: Any, platform: str, item_id: str, **kwargs: Any) -> dict[str, Any]:
        fetched.append(item_id)
        return {"ok": True, "platform": platform, "items": [_detail(item_id, want=str(len(fetched) * 10))]}

    ctx = make_ctx()
    with patch.object(
        select_tool,
        "search_items",
        _fake_search({"甲": ["a1", "a2"], "乙": ["b1", "b2"], "丙": ["c1", "c2"]}),
    ), patch.object(select_tool, "fetch_detail", fake_detail):
        out = asyncio.run(
            select_tool.select_products(ctx, keywords=["甲", "乙", "丙"], details_per_keyword=1)
        )

    # 每个候选恰好一条，而不是第一个候选把预算吃光。
    assert sorted(fetched) == ["a1", "b1", "c1"]
    assert len(out["candidates"]) == 3
    assert all(row["detail_size"] == 1 for row in out["candidates"])
    # 三个候选都量到了需求 → 需求热度这个维度算得出来（不再是「无法归一」）。
    assert all(row["dimensions"].get("demand") is not None for row in out["candidates"])


def test_detail_failure_excludes_only_that_candidate() -> None:
    """一个候选撞风控 → 它进 excluded 并记 issue，另一个候选照常出分。"""
    async def fake_detail(ctx: Any, platform: str, item_id: str, **kwargs: Any) -> dict[str, Any]:
        if item_id.startswith("bad"):
            return {"ok": False, "platform": platform, "items": [], "error_code": "channel.risk", "message": "风控"}
        return {"ok": True, "platform": platform, "items": [_detail(item_id)]}

    ctx = make_ctx()
    with patch.object(select_tool, "search_items", _fake_search({"坏词": ["bad1"], "好词": ["good1", "good2", "good3"]})), \
         patch.object(select_tool, "fetch_detail", fake_detail):
        out = asyncio.run(
            select_tool.select_products(ctx, keywords=["坏词", "好词"], details_per_keyword=1)
        )

    assert out["ok"] is True
    keywords = [row["keyword"] for row in out["candidates"]]
    assert "好词" in keywords
    # 坏词的壳子还在，只是没量到需求 —— 它仍然算一个候选，不该被冒充成结论。
    assert any(issue["error_code"] == "channel.risk" for issue in out["issues"])
    assert "坏词" not in [row["keyword"] for row in out["excluded"]]


def test_search_failure_lands_in_excluded_not_candidates() -> None:
    """搜索直接挂掉 → 该候选进 ``excluded``（带码），且不进候选表。"""
    async def fake_search(ctx: Any, platform: str, query: str, limit: int = 30) -> dict[str, Any]:
        if query == "挂掉的词":
            return {"ok": False, "platform": platform, "items": [], "error_code": "account.session_expired", "message": "登录失效"}
        return {"ok": True, "platform": platform, "items": [_shell("g1"), _shell("g2"), _shell("g3")]}

    async def fake_detail(ctx: Any, platform: str, item_id: str, **kwargs: Any) -> dict[str, Any]:
        return {"ok": True, "platform": platform, "items": [_detail(item_id)]}

    ctx = make_ctx()
    with patch.object(select_tool, "search_items", fake_search), \
         patch.object(select_tool, "fetch_detail", fake_detail):
        out = asyncio.run(
            select_tool.select_products(ctx, keywords=["挂掉的词", "好词"], details_per_keyword=1)
        )

    assert [row["keyword"] for row in out["candidates"]] == ["好词"]
    assert [row["keyword"] for row in out["excluded"]] == ["挂掉的词"]
    assert out["excluded"][0]["error_code"] == "account.session_expired"


def test_all_failed_returns_dominant_error_code() -> None:
    """全部取不到样本 → ``ok=False``，``error_code`` 取出现最多的那个码。"""
    async def fake_search(ctx: Any, platform: str, query: str, limit: int = 30) -> dict[str, Any]:
        code = "channel.risk" if query != "登录词" else "account.session_expired"
        return {"ok": False, "platform": platform, "items": [], "error_code": code, "message": code}

    ctx = make_ctx()
    with patch.object(select_tool, "search_items", fake_search), \
         patch.object(select_tool, "fetch_detail", _never_called):
        out = asyncio.run(
            select_tool.select_products(
                ctx, keywords=["风控词", "也风控", "登录词"], details_per_keyword=1
            )
        )

    assert out["ok"] is False
    assert out["candidates"] == []
    assert out["error_code"] == "channel.risk"
    assert len(out["excluded"]) == 3


async def _never_called(ctx: Any, platform: str, item_id: str, **kwargs: Any) -> dict[str, Any]:
    raise AssertionError("搜索就失败了，不该去拉详情")


def test_payload_does_not_look_like_a_product_list() -> None:
    """出参不许带顶层 ``platform`` + ``items``。

    前端 ``extractProducts`` 看到这两个键就会把结果吞进商品面板 —— 候选表会被当成
    商品列表渲染，而它根本不是商品。所以平台放 ``platforms``（复数），候选放 ``candidates``。
    """
    async def fake_detail(ctx: Any, platform: str, item_id: str, **kwargs: Any) -> dict[str, Any]:
        return {"ok": True, "platform": platform, "items": [_detail(item_id)]}

    ctx = make_ctx()
    with patch.object(select_tool, "search_items", _fake_search({"甲": ["a1", "a2", "a3"]})), \
         patch.object(select_tool, "fetch_detail", fake_detail):
        out = asyncio.run(select_tool.select_products(ctx, keywords=["甲"], details_per_keyword=2))

    assert out["kind"] == "product_selection"
    assert "platform" not in out
    assert "items" not in out
    assert out["platforms"] == ["xianyu"]
    assert out["candidates"][0]["sample_size"] == 3


def test_unsupported_platform_is_rejected() -> None:
    """拼多多这种没接的平台直接拒掉，别让它变成一个空候选混进结论。"""
    ctx = make_ctx()
    out = asyncio.run(select_tool.select_products(ctx, keywords=["甲"], platforms=["pinduoduo"]))
    assert out["ok"] is False
    assert out["error_code"] == "agent.invalid_input"


def test_empty_keywords_are_rejected() -> None:
    ctx = make_ctx()
    out = asyncio.run(select_tool.select_products(ctx, keywords=["   "], platforms=["xianyu"]))
    assert out["ok"] is False
    assert out["error_code"] == "agent.invalid_input"


def test_input_caps_are_enforced_by_schema() -> None:
    """上限写在校验里，不写在提示词里 —— 模型多要也要不上去。"""
    import pydantic

    try:
        select_tool.SelectInput(keywords=["a", "b", "c", "d"])
    except pydantic.ValidationError:
        pass
    else:
        raise AssertionError("keywords 超过 3 个应当被拒")

    try:
        select_tool.SelectInput(keywords=["a"], details_per_keyword=9)
    except pydantic.ValidationError:
        pass
    else:
        raise AssertionError("details_per_keyword 超过 3 应当被拒")
