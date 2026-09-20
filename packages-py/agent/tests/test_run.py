"""运行入口单测：登录门禁（ensure_logins）与一轮编排（run_chat）。

- 门禁三平台并发校验，全有效就不扫码；有失效才对失效平台逐个扫码。
- run_chat：门禁过 → 主编排；取消在门禁后、主编排前也要能干净收尾。
真实扫码/浏览器都 patch 掉，只验证分支走向与退出码。本仓无 pytest-asyncio，
测试统一写成 sync + ``asyncio.run``（同 test_loop.py）。
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from langchain_core.messages import AIMessage

from agent.context import AuthSnapshot, RunContext
from agent.run import EXIT_CANCELLED, ensure_logins, run_chat
from agent.sse import EventBus
from agent.subagents import crawler as crawler_sub
from conftest import FakeLlm, ScriptedChat, make_ctx


def _ctx_with(checker) -> RunContext:
    return make_ctx(auth_checker=checker)


def test_ensure_logins_skips_scan_when_all_valid() -> None:
    """三平台都有效：不调用扫码登录。"""
    bus = EventBus("r")
    checker = lambda platform, _: AuthSnapshot(auth_valid=True, has_cookie=True)
    ctx = _ctx_with(checker)

    with patch("agent.run.login_blocking", new=AsyncMock(return_value={"ok": True})) as blk:
        asyncio.run(ensure_logins(bus, ctx=ctx))

    blk.assert_not_called()


def test_ensure_logins_scans_only_failed_platforms() -> None:
    """只有 xianyu 有效：小红书与 1688 各扫一次，xianyu 不扫。"""

    def checker(platform: str, _):
        return AuthSnapshot(auth_valid=platform == "xianyu", has_cookie=platform == "xianyu")

    bus = EventBus("r")
    ctx = _ctx_with(checker)
    scanned: dict[str, bool] = {}

    async def fake_login(platform: str, c: RunContext, **_kwargs: object) -> dict:
        scanned[platform] = True
        return {"ok": True}

    with patch("agent.run.login_blocking", fake_login):
        asyncio.run(ensure_logins(bus, ctx=ctx))

    assert scanned == {"xiaohongshu": True, "ali1688": True}
    assert "xianyu" not in scanned


def test_run_chat_happy_path_returns_ok() -> None:
    """门禁过 + 主编排 crawl→finish：退出码 0。"""
    bus = EventBus("r")
    checker = lambda platform, _: AuthSnapshot(auth_valid=True, has_cookie=True)
    ctx = make_ctx(
        auth_checker=checker,
        llm=FakeLlm(ScriptedChat(script=[
            AIMessage(content="", tool_calls=[{"name": "crawl", "args": {"task": "搜"}, "id": "c1"}]),
            AIMessage(content="", tool_calls=[{"name": "finish", "args": {"summary": "好"}, "id": "c2"}]),
        ])),
    )

    async def fake_crawl(c: object, task: str) -> dict:
        return {"ok": True, "items": [], "issues": [], "summary": "ok"}

    with patch.object(crawler_sub, "run_crawler", fake_crawl):
        code = asyncio.run(run_chat(bus=bus, ctx=ctx, prompt="搜"))

    assert code == 0


def test_run_chat_cancelled_before_orchestrator() -> None:
    """门禁前就取消：发 error 帧并以 EXIT_CANCELLED 收尾，不进主编排。"""
    bus = EventBus("r")
    cancel = asyncio.Event()
    cancel.set()
    checker = lambda platform, _: AuthSnapshot(auth_valid=True, has_cookie=True)
    ctx = make_ctx(auth_checker=checker, cancel=cancel)

    code = asyncio.run(run_chat(bus=bus, ctx=ctx, prompt="搜"))
    assert code == EXIT_CANCELLED
