"""子 agent 单测：crawler / repair / validator 的取数与汇总口径。

这里不真开浏览器 —— 把 ``tools/*`` 的 ``TOOLS`` 换成假工具（子 agent 在运行时读
``crawl.TOOLS`` 等模块属性，patch 即可生效），用脚本假模型驱动循环，验证各子 agent
的 ``_collect`` 汇总逻辑：去重、issues 收口、选择器提取、valid/hot_reloaded 分离。
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

from langchain_core.messages import AIMessage

from agent.loop import ToolSpec
from agent.subagents.crawler import run_crawler
from agent.subagents.repair import run_repair
from agent.subagents.validator import run_validate
from agent.tools import crawl as crawl_tools, repair as repair_tools, validate as validate_tools
from agent.tools.crawl import DetailInput, SearchInput
from agent.tools.repair import InspectInput, SubmitInput
from agent.tools.validate import CommitInput, TryInput
from conftest import FakeLlm, ScriptedChat, make_ctx


# ---- 假工具：替代真实浏览器工具，只回构造好的 dict ----


async def _fake_search(ctx: Any, platform: str, query: str, limit: int = 30) -> dict[str, Any]:
    return {
        "ok": True,
        "platform": platform,
        "items": [
            {"platform": platform, "item_id": "i1", "title": "A"},
            {"platform": platform, "item_id": "i1", "title": "A"},  # 重复
            {"platform": platform, "item_id": "i2", "title": "B"},
        ],
        "query": query,
    }


async def _fake_detail(ctx: Any, platform: str, item_id: str, xsec_token: str | None = None, url: str | None = None) -> dict[str, Any]:
    return {"ok": True, "platform": platform, "items": [{"platform": platform, "item_id": item_id, "title": "D"}]}


FAKE_CRAWL_TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(name="search_items", label="搜索", description="", args=SearchInput, fn=_fake_search, browser=False),
    ToolSpec(name="fetch_detail", label="详情", description="", args=DetailInput, fn=_fake_detail, browser=False),
)


async def _fake_inspect(ctx: Any, platform: str, item_id: str, **kwargs: Any) -> dict[str, Any]:
    return {"ok": True, "platform": platform, "required_fields": ["title", "price"], "current_selectors": {}}


async def _fake_submit(ctx: Any, platform: str, item_id: str, selectors: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "platform": platform, "selectors": selectors}


FAKE_REPAIR_TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(name="inspect_dom", label="检查 DOM", description="", args=InspectInput, fn=_fake_inspect, browser=False),
    ToolSpec(name="submit_patch", label="提交选择器", description="", args=SubmitInput, fn=_fake_submit, browser=False),
)


async def _fake_try(ctx: Any, platform: str, item_id: str, selectors: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    return {"ok": True, "platform": platform, "valid": True, "payload": {"title": "x"}}


async def _fake_commit(ctx: Any, platform: str, selectors: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    return {"ok": True, "platform": platform}


FAKE_VALIDATE_TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(name="try_selectors", label="验证", description="", args=TryInput, fn=_fake_try, browser=False),
    ToolSpec(name="commit_selectors", label="热更新", description="", args=CommitInput, fn=_fake_commit, browser=False),
)


def test_run_crawler_dedupes_items_and_attaches_issues() -> None:
    """搜索出两条 i1（含重复）+ 详情 i2：去重后只剩 i1、i2 两条。"""
    ctx = make_ctx(llm=FakeLlm(ScriptedChat(script=[
        AIMessage(content="", tool_calls=[{"name": "search_items", "args": {"platform": "xianyu", "query": "手机", "limit": 10}, "id": "c1"}]),
        AIMessage(content="", tool_calls=[{"name": "fetch_detail", "args": {"platform": "xianyu", "item_id": "i2"}, "id": "c2"}]),
        AIMessage(content="拿到了"),
    ])))
    with patch.object(crawl_tools, "TOOLS", FAKE_CRAWL_TOOLS):
        out = asyncio.run(run_crawler(ctx, "搜 xianyu 手机"))

    assert out["ok"] is True
    ids = [it["item_id"] for it in out["items"]]
    assert sorted(ids) == ["i1", "i2"]
    assert len(out["items"]) == 2  # i1 的重复被并掉


def test_run_crawler_aggregates_issues_from_failed_tool() -> None:
    """搜索失败要进 issues，且 ok 随失败翻 False。"""

    async def _bad(ctx: Any, platform: str, query: str, limit: int = 30) -> dict[str, Any]:
        return {"ok": False, "platform": platform, "error_code": "crawler.needs_repair", "message": "抽不到"}

    fake = (ToolSpec(name="search_items", label="搜索", description="", args=SearchInput, fn=_bad, browser=False),)
    ctx = make_ctx(llm=FakeLlm(ScriptedChat(script=[
        AIMessage(content="", tool_calls=[{"name": "search_items", "args": {"platform": "xianyu", "query": "手机"}, "id": "c1"}]),
        AIMessage(content="空空如也"),
    ])))
    with patch.object(crawl_tools, "TOOLS", fake):
        out = asyncio.run(run_crawler(ctx, "搜 xianyu 手机"))

    assert out["ok"] is False
    assert out["issues"][0]["error_code"] == "crawler.needs_repair"
    assert out["issues"][0]["platform"] == "xianyu"


def test_run_repair_submits_selectors_via_stop_tool() -> None:
    """修复子 agent：inspect → submit_patch 收尾，选择器从 stop_args 出来。"""
    ctx = make_ctx(llm=FakeLlm(ScriptedChat(script=[
        AIMessage(content="", tool_calls=[{"name": "inspect_dom", "args": {"platform": "xianyu", "item_id": "i1"}, "id": "c1"}]),
        AIMessage(content="", tool_calls=[{"name": "submit_patch", "args": {"platform": "xianyu", "item_id": "i1", "selectors": {"title": ".t", "price": ".p"}}, "id": "c2"}]),
    ])))
    with patch.object(repair_tools, "TOOLS", FAKE_REPAIR_TOOLS):
        out = asyncio.run(run_repair(ctx, platform="xianyu", item_id="i1"))

    assert out["ok"] is True
    assert out["selectors"] == {"title": ".t", "price": ".p"}
    assert out["issues"] == []  # 没撞墙


def test_run_validate_marks_valid_and_hot_reloaded() -> None:
    """验证通过并热更新：valid 与 hot_reloaded 都为 True，ok 才 True。"""
    ctx = make_ctx(llm=FakeLlm(ScriptedChat(script=[
        AIMessage(content="", tool_calls=[{"name": "try_selectors", "args": {"platform": "xianyu", "item_id": "i1", "selectors": {"title": ".t"}}, "id": "c1"}]),
        AIMessage(content="", tool_calls=[{"name": "commit_selectors", "args": {"platform": "xianyu", "selectors": {"title": ".t"}}, "id": "c2"}]),
        AIMessage(content="通过且已热更新"),
    ])))
    with patch.object(validate_tools, "TOOLS", FAKE_VALIDATE_TOOLS):
        out = asyncio.run(run_validate(ctx, platform="xianyu", item_id="i1", selectors={"title": ".t"}))

    assert out["ok"] is True
    assert out["valid"] is True
    assert out["hot_reloaded"] is True


def test_run_validate_no_commit_when_try_fails() -> None:
    """试选择器失败就如实回报，绝不调 commit_selectors 写盘。"""

    async def _fail(ctx: Any, platform: str, item_id: str, selectors: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
        return {"ok": False, "platform": platform, "error_code": "crawler.validate_failed", "message": "没抽到"}

    fake = (ToolSpec(name="try_selectors", label="验证", description="", args=TryInput, fn=_fail, browser=False), ToolSpec(name="commit_selectors", label="热更新", description="", args=CommitInput, fn=_fake_commit, browser=False))
    ctx = make_ctx(llm=FakeLlm(ScriptedChat(script=[
        AIMessage(content="", tool_calls=[{"name": "try_selectors", "args": {"platform": "xianyu", "item_id": "i1", "selectors": {"title": ".t"}}, "id": "c1"}]),
        AIMessage(content="没抽到，不改"),
    ])))
    with patch.object(validate_tools, "TOOLS", fake):
        out = asyncio.run(run_validate(ctx, platform="xianyu", item_id="i1", selectors={"title": ".t"}))

    assert out["valid"] is False
    assert out["hot_reloaded"] is False  # 没写盘
    assert out["ok"] is False
    assert out["issues"][0]["error_code"] == "crawler.validate_failed"
