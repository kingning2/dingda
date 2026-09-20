"""人工风控窗口单测：通过判定与专用浏览器生命周期。"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

from agent.tools import risk as risk_tools
from conftest import make_ctx


class _FakePage:
    """一个正文已渲染、旧 URL 仍带验证标记的假页面。"""

    url = "https://example.com/verify?ticket=done"
    title = "验证"

    async def goto(self, target: str) -> None:
        """打开目标页。"""

    async def screenshot(self) -> bytes:
        """返回一帧假截图。"""
        return b"frame"

    async def evaluate(self, expression: str, arg: Any = None) -> str:
        """返回足够长的普通正文。"""
        return "商品已经打开" + "详情内容" * 40


def test_manual_window_passes_on_body_and_closes_browser() -> None:
    """人工窗口用正文判定通过，并且使用专用会话立刻关掉浏览器。"""
    calls: dict[str, Any] = {}

    @asynccontextmanager
    async def fake_crawl_session(platform: str, **kwargs: Any):
        calls["platform"] = platform
        calls.update(kwargs)
        crawler = SimpleNamespace(
            open_page=lambda ctx: _open(),
            close_page=lambda page: _close(),
        )
        yield SimpleNamespace(crawler=crawler, ctx=lambda **extra: SimpleNamespace())

    async def _open():
        calls["opened"] = True
        return _FakePage()

    async def _close():
        calls["closed"] = True

    ctx = make_ctx()
    with patch.object(risk_tools, "crawl_session", fake_crawl_session), \
         patch.object(risk_tools, "_POLL_INTERVAL_S", 0), \
         patch.object(risk_tools, "_CLEAR_HOLD_S", 0):
        result = asyncio.run(risk_tools.open_headed_browser(ctx, "xianyu", url="https://example.com"))

    assert result["ok"] is True
    assert calls["dedicated"] is True
    assert calls["headless"] is False
    assert calls["opened"] is True
    assert calls["closed"] is True


def test_risk_page_judgement_uses_body() -> None:
    """旧验证 URL 不该拦住已渲染正文；正文含风控文案仍要继续等。"""
    body = "商品已经打开" + "详情内容" * 40
    assert risk_tools._looks_blocked("https://example.com/verify", "验证", body) is False
    assert risk_tools._looks_blocked("https://example.com", "首页", "滑动验证开始") is True
