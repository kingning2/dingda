"""主编排单测：决策与派活口径。

子 agent（crawler/repair/validate）用 ``patch`` 换成假实现，避免真开浏览器；只验证
主编排**怎么判断、派什么活、按什么顺序**：够不够、撞 ``crawler.needs_repair`` 要不要
走修复+验证、撞 ``channel.risk`` 要不要开有头窗口。风控兜底要走 ``risk.TOOLS``
（循环在运行时读它），所以单独 patch 那一节。
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

from langchain_core.messages import AIMessage

from agent.loop import ToolSpec
from agent.orchestrator import _is_decision_request, run_orchestrator
from agent.subagents import crawler as crawler_sub, repair as repair_sub, validator as validator_sub
from agent.tools import appraise as appraise_tools
from agent.tools import risk as risk_tools
from agent.tools import select as select_tools
from agent.tools.appraise import AppraiseInput
from agent.tools.risk import HeadedInput
from agent.tools.select import SelectInput
from conftest import FakeLlm, ScriptedChat, make_ctx


def test_orchestrator_crawls_then_finishes() -> None:
    """一条任务：派一次爬虫就拿到了，直接 finish 交总结。"""
    ctx = make_ctx(llm=FakeLlm(ScriptedChat(script=[
        AIMessage(content="", tool_calls=[{"name": "crawl", "args": {"task": "搜 xianyu 手机"}, "id": "c1"}]),
        AIMessage(content="", tool_calls=[{"name": "finish", "args": {"summary": "拿到 3 条"}, "id": "c2"}]),
    ])))
    calls: list[str] = []

    async def fake_crawl(c: Any, task: str) -> dict[str, Any]:
        calls.append(task)
        return {"ok": True, "items": [{"platform": "xianyu", "item_id": "x1"}], "issues": [], "summary": "ok"}

    with patch.object(crawler_sub, "run_crawler", fake_crawl):
        out = asyncio.run(run_orchestrator(ctx, "搜 xianyu 手机"))

    assert out["ok"] is True
    assert out["summary"] == "拿到 3 条"
    assert calls == ["搜 xianyu 手机"]


def test_orchestrator_repairs_when_crawler_needs_repair() -> None:
    """爬虫报 needs_repair：主编排依次派 修复 → 验证 → 重新爬，最后 finish。"""
    ctx = make_ctx(llm=FakeLlm(ScriptedChat(script=[
        AIMessage(content="", tool_calls=[{"name": "crawl", "args": {"task": "搜"}, "id": "c1"}]),
        AIMessage(content="", tool_calls=[{"name": "repair_selectors", "args": {"platform": "xianyu", "item_id": "i1"}, "id": "c2"}]),
        AIMessage(content="", tool_calls=[{"name": "validate_selectors", "args": {"platform": "xianyu", "item_id": "i1", "selectors": {"title": ".t"}}, "id": "c3"}]),
        AIMessage(content="", tool_calls=[{"name": "crawl", "args": {"task": "重爬 i1"}, "id": "c4"}]),
        AIMessage(content="", tool_calls=[{"name": "finish", "args": {"summary": "修好重爬拿到"}, "id": "c5"}]),
    ])))
    seq: list[tuple[str, str]] = []

    async def fake_crawl(c: Any, task: str) -> dict[str, Any]:
        seq.append(("crawl", task))
        if "重爬" in task:
            return {"ok": True, "items": [{"platform": "xianyu", "item_id": "x2"}], "issues": [], "summary": "ok"}
        return {"ok": False, "items": [], "issues": [{"tool": "search_items", "platform": "xianyu", "error_code": "crawler.needs_repair", "message": "抽不到"}], "summary": "空"}

    async def fake_repair(c: Any, *, platform: str, item_id: str, **kwargs: Any) -> dict[str, Any]:
        seq.append(("repair", platform))
        return {"ok": True, "platform": platform, "item_id": item_id, "selectors": {"title": ".t"}, "issues": [], "summary": "候选"}

    async def fake_validate(c: Any, *, platform: str, item_id: str, selectors: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        seq.append(("validate", platform))
        return {"ok": True, "platform": platform, "item_id": item_id, "valid": True, "hot_reloaded": True, "issues": [], "summary": "通过"}

    with patch.object(crawler_sub, "run_crawler", fake_crawl), \
         patch.object(repair_sub, "run_repair", fake_repair), \
         patch.object(validator_sub, "run_validate", fake_validate):
        out = asyncio.run(run_orchestrator(ctx, "搜 xianyu"))

    assert out["ok"] is True
    kinds = [step[0] for step in seq]
    assert kinds == ["crawl", "repair", "validate", "crawl"]


def test_orchestrator_opens_headed_browser_on_risk() -> None:
    """爬虫报 channel.risk：自动过失败后，主编排开有头窗口让用户手动过。"""
    ctx = make_ctx(llm=FakeLlm(ScriptedChat(script=[
        AIMessage(content="", tool_calls=[{"name": "crawl", "args": {"task": "搜"}, "id": "c1"}]),
        AIMessage(content="", tool_calls=[{"name": "open_headed_browser", "args": {"platform": "xianyu", "item_id": "i1"}, "id": "c2"}]),
        AIMessage(content="", tool_calls=[{"name": "finish", "args": {"summary": "风控已过"}, "id": "c3"}]),
    ])))
    risk_calls: list[str] = []

    async def fake_crawl(c: Any, task: str) -> dict[str, Any]:
        return {"ok": False, "items": [], "issues": [{"error_code": "channel.risk", "platform": "xianyu", "message": "风控"}], "summary": "风控"}

    async def fake_risk(c: Any, platform: str, url: str | None = None, item_id: str | None = None) -> dict[str, Any]:
        risk_calls.append(platform)
        return {"ok": True, "platform": platform, "message": "过"}

    fake_risk_tools = (ToolSpec(name="open_headed_browser", label="人工过风控", description="", args=HeadedInput, fn=fake_risk, browser=True),)
    with patch.object(crawler_sub, "run_crawler", fake_crawl), \
         patch.object(risk_tools, "TOOLS", fake_risk_tools):
        out = asyncio.run(run_orchestrator(ctx, "搜 xianyu"))

    assert out["ok"] is True
    assert risk_calls == ["xianyu"]


def test_decision_request_routes_to_select_products() -> None:
    """「不知道该卖什么」→ 调 select_products，**不**调 crawl。

    这是本功能的核心断言：以前模型会自己编个关键词去 crawl，再把商品列表当结论。
    """
    ctx = make_ctx(llm=FakeLlm(ScriptedChat(script=[
        AIMessage(content="", tool_calls=[{"name": "select_products", "args": {"keywords": ["露营折叠桌", "车载收纳箱"]}, "id": "c1"}]),
        AIMessage(content="", tool_calls=[{"name": "finish", "args": {"summary": "推露营折叠桌"}, "id": "c2"}]),
    ])))
    crawled: list[str] = []
    selected: list[list[str]] = []

    async def fake_crawl(c: Any, task: str) -> dict[str, Any]:
        crawled.append(task)
        return {"ok": True, "items": [], "issues": [], "summary": "不该被调到"}

    async def fake_select(c: Any, keywords: list[str], **kwargs: Any) -> dict[str, Any]:
        selected.append(list(keywords))
        return {"ok": True, "kind": "product_selection", "platforms": ["xianyu"], "candidates": [{"keyword": keywords[0], "score": 71.1}]}

    fake_select_tools = (
        ToolSpec(name="select_products", label="选品 · {platform}", description="", args=SelectInput, fn=fake_select, browser=True),
    )
    with patch.object(crawler_sub, "run_crawler", fake_crawl), \
         patch.object(select_tools, "TOOLS", fake_select_tools):
        out = asyncio.run(
            run_orchestrator(ctx, "我是个零基础的电商新手，完全不知道自己该卖什么。你直接替我做决定：告诉我到底该卖什么")
        )

    assert out["ok"] is True
    assert selected == [["露营折叠桌", "车载收纳箱"]]
    assert crawled == [], "选品请求不该退化成一次 crawl"


def test_plain_data_request_is_not_flagged_as_decision() -> None:
    """给了明确关键词就是在取数，不该被钉选品指令。"""
    assert _is_decision_request("帮我查一下闲鱼上折叠桌的行情") is False
    assert _is_decision_request("我是个零基础新手，不知道该卖什么") is True


def test_item_link_routes_to_appraise_item() -> None:
    """给了一个具体商品问「值不值得买」→ 调 appraise_item，**不**退化成一次 crawl。

    这是鉴定功能的核心断言：以前没有这个工具时，模型只能自己编个关键词去搜，
    再把商品列表包装成一个「建议」—— 而用户问的是**这一件**。
    """
    ctx = make_ctx(llm=FakeLlm(ScriptedChat(script=[
        AIMessage(content="", tool_calls=[{"name": "appraise_item", "args": {"platform": "xianyu", "item_id": "123456789"}, "id": "c1"}]),
        AIMessage(content="", tool_calls=[{"name": "finish", "args": {"summary": "不值得买"}, "id": "c2"}]),
    ])))
    crawled: list[str] = []
    appraised: list[tuple[str, str]] = []

    async def fake_crawl(c: Any, task: str) -> dict[str, Any]:
        crawled.append(task)
        return {"ok": True, "items": [], "issues": [], "summary": "不该被调到"}

    async def fake_appraise(c: Any, platform: str = "xianyu", item_id: str = "", **kwargs: Any) -> dict[str, Any]:
        appraised.append((platform, item_id))
        return {"ok": True, "kind": "product_appraisal", "verdict": "skip", "verdict_label": "不值得", "comparables": []}

    fake_appraise_tools = (
        ToolSpec(name="appraise_item", label="鉴定 · {platform}", description="", args=AppraiseInput, fn=fake_appraise, browser=True),
    )
    with patch.object(crawler_sub, "run_crawler", fake_crawl), \
         patch.object(appraise_tools, "TOOLS", fake_appraise_tools):
        out = asyncio.run(
            run_orchestrator(ctx, "这个 https://www.goofish.com/item?id=123456789 值不值得买")
        )

    assert out["ok"] is True
    assert appraised == [("xianyu", "123456789")]
    assert crawled == [], "鉴定请求不该退化成一次 crawl"


def test_appraisal_request_is_not_flagged_as_decision() -> None:
    """「这一件值不值得买」是商品级提问，不是选品意图 —— 别钉错指令。

    钉成选品的话，模型会被推去提候选品类，而用户问的是手里这一件。
    """
    assert _is_decision_request("这个链接的商品值不值得买 https://www.goofish.com/item?id=123456789") is False
    assert _is_decision_request("帮我看看这个能不能买来转卖") is False


def test_appraisal_phrasing_beats_the_decision_hint() -> None:
    """措辞里带「帮我选」但问的是**具体商品**时，不算选品请求。

    这是修过的一处口径冲突：「帮我选」原片在选品词表里，于是「帮我选一下这个
    值不值得买」会被钉上「必须先调 select_products」的硬指令 —— 而用户问的是
    手里这一件。两条例外（给了商品链接 / 用了鉴定语气）都指向同一件事。
    """
    # 鉴定语气
    assert _is_decision_request("帮我选一下这个值得买吗") is False
    assert _is_decision_request("帮我看看这个能不能买来转卖") is False
    # 给了链接
    assert _is_decision_request("帮我选个 https://www.goofish.com/item?id=123456789 到底值不值得买") is False
    # 真的是选品：没给商品、也没有鉴定语气 —— 仍然要钉
    assert _is_decision_request("我完全不知道该卖什么，帮我选一个方向") is True
    assert _is_decision_request("帮我选品") is True


_TARGET_ID = "123456789"

_TARGET = {
    "item_id": _TARGET_ID,
    "title": "【清仓】露营折叠桌 全新包邮",
    "price": "10",
    "want_count": "200",
    "browse_count": "2000",
    "sold_state": "on_sale",
    "seller_nick": "我",
    "url": f"https://example.com/item/{_TARGET_ID}",
}


def _peer_shell(item_id: str, *, price: str) -> dict[str, Any]:
    return {
        "item_id": item_id,
        "title": f"同款 {item_id}",
        "url": f"https://example.com/item/{item_id}",
        "platform": "xianyu",
        "price": price,
        "seller_nick": f"卖家{item_id}",
    }


def _peer_detail(item_id: str) -> dict[str, Any]:
    return {
        **_peer_shell(item_id, price="40"),
        "want_count": "5",
        "browse_count": "50",
        "sold_state": "on_sale",
    }


def test_real_appraise_tool_survives_the_whole_loop() -> None:
    """**真工具**跑通整条链：build_tools → 入参校验 → 真 handler → 真打分器。

    上面那条 ``test_item_link_routes_to_appraise_item`` 把 ``appraise_tools.TOOLS``
    整个换成了假的 —— 它只证明**名字被认出来了**，不证明真工具在循环里活得下来：
    入参能不能过 pydantic、``_specs()`` 展开的登记项形状对不对、handler 拿到的
    ``ctx`` 是不是循环那个、出参能不能被 ``_as_dict`` 收成 dict、``browser=True``
    的步骤块发不发得出去。这条把 TOOLS 留成真的，只在爬虫原语上打桩。

    断言的是**工具出参**（从 ``toolResult`` 事件里取，就是前端折叠区看到的那份），
    不是循环的返回值 —— 循环只回 ``exit_code``，出参要是错了用户那边就是错的。
    """
    ctx = make_ctx(
        emit=None,
        llm=FakeLlm(ScriptedChat(script=[
            AIMessage(
                content="我来看看这一件。",
                tool_calls=[{
                    "name": "appraise_item",
                    "args": {"platform": "xianyu", "item_id": _TARGET_ID, "details": 3},
                    "id": "c1",
                }],
            ),
            AIMessage(content="", tool_calls=[{"name": "finish", "args": {"summary": "鉴定完了"}, "id": "c2"}]),
        ])),
    )
    events: list[dict[str, Any]] = []
    ctx.emit = events.append
    ctx.live = True

    fetched: list[str] = []
    queries: list[str] = []

    async def fake_search(c: Any, platform: str, query: str, limit: int = 30) -> dict[str, Any]:
        queries.append(query)
        return {
            "ok": True,
            "platform": platform,
            "items": [
                _peer_shell(_TARGET_ID, price="10"),  # 搜索结果里也含本商品自己
                _peer_shell("a", price="40"),
                _peer_shell("b", price="45"),
                _peer_shell("c", price="55"),
            ],
        }

    async def fake_detail(
        c: Any,
        platform: str,
        item_id: str,
        xsec_token: str | None = None,
        url: str | None = None,
    ) -> dict[str, Any]:
        fetched.append(item_id)
        if item_id == _TARGET_ID:
            return {"ok": True, "platform": platform, "items": [dict(_TARGET)], "issues": []}
        return {"ok": True, "platform": platform, "items": [_peer_detail(item_id)], "issues": []}

    with patch.object(appraise_tools, "search_items", fake_search), \
         patch.object(appraise_tools, "fetch_detail", fake_detail):
        out = asyncio.run(
            run_orchestrator(ctx, "这个 https://www.goofish.com/item?id=123456789 值不值得买")
        )

    assert out["ok"] is True

    results = [e for e in events if e.get("type") == "toolResult" and e.get("output", {}).get("kind") == "product_appraisal"]
    assert len(results) == 1, f"没拿到鉴定出参，事件里只有 {[e.get('type') for e in events]}"
    payload = results[0]["output"]

    # 形状：真打分器给的四态判词，而不是一个 ok=False 的兜底
    assert payload["ok"] is True, payload.get("message")
    assert payload["verdict"] in {"worth", "caution", "skip", "insufficient"}
    assert payload["verdict_label"]
    assert payload["reasons"], "判词没有理由，用户看不出分是怎么来的"
    assert payload["verdict_reason"]

    # 本商品在本商品那一行，不在同款里
    assert payload["target"]["item_id"] == _TARGET_ID
    peers = [row["item_id"] for row in payload["comparables"] if not row.get("is_target")]
    assert _TARGET_ID not in peers, "本商品被自己当成同款了 —— 中位价会被自己拉平"
    assert [row["item_id"] for row in payload["comparables"] if row.get("is_target")] == [_TARGET_ID]
    assert len(peers) == 3

    # 取数路径：本商品只拉一次详情；同款详情不超过 details；检索词是从标题截的并在出参回显
    assert fetched[0] == _TARGET_ID
    assert fetched.count(_TARGET_ID) == 1
    assert len(fetched) == 4, f"详情条数没被 details 卡住：{fetched}"
    assert queries == ["露营折叠桌"]
    assert payload["query"] == "露营折叠桌"

    # 步骤块：browser=True 的登记项在事件里；出参按价格升序
    assert any(e.get("type") == "toolCall" and e.get("name") == "appraise_item" for e in events)
    prices = [row.get("price") for row in payload["comparables"]]
    assert prices == sorted(prices, key=lambda p: float(p or 0))
