"""闲鱼人工滑块等待：正向判定 + Cookie 回写回归测试（不启浏览器）。"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from contracts.browser_port import Cookie
from channels.xianyu import risk_recovery as recovery
from core.errors import AppError

_ITEM_URL = "https://www.goofish.com/item?id=1038069226293"


class _FakeRaw:
    """假 raw page：无滑块元素，正文由测试指定。"""

    def __init__(self, *, body: str = "", blocked: bool = False) -> None:
        self.body = body
        self.blocked = blocked
        self.frames: list[Any] = []

    @property
    def url(self) -> str:
        if self.blocked:
            return "https://passport.goofish.com/_____tmd_____/punish"
        return _ITEM_URL

    async def evaluate(self, expression: str, arg: Any = None) -> Any:
        return self.body

    async def query_selector(self, selector: str) -> Any:
        return None


class _FakeHeaded:
    """假有头窗口 Page：记录轮询次数。"""

    def __init__(self, raw: _FakeRaw) -> None:
        self.raw = raw
        self.polls = 0
        self.closed = False

    @property
    def url(self) -> str:
        return self.raw.url

    async def goto(self, url: str, **_: Any) -> None:
        return None

    async def evaluate(self, expression: str, arg: Any = None) -> Any:
        self.polls += 1
        return self.raw.body

    async def cookies(self) -> list[Cookie]:
        return [Cookie(name="x5sec", value="passed", domain=".goofish.com")]

    async def close(self) -> None:
        self.closed = True


class _FakeOrigin:
    """被恢复的原 page（爬虫那台无头页）。"""

    def __init__(self) -> None:
        self.added: list[Cookie] = []

    async def cookies(self) -> list[Cookie]:
        return []

    async def add_cookies(self, cookies: Any, *, default_domain: str = "") -> None:
        self.added = list(cookies)


class _FakePort:
    def __init__(self, headed: _FakeHeaded) -> None:
        self._headed = headed

    async def open(self, **_: Any) -> _FakeHeaded:
        return self._headed


class _FakeManager:
    """假 BrowserManager：构造即返回自身，acquire 直接给有头窗口。"""

    def __init__(self, headed: _FakeHeaded) -> None:
        self._headed = headed
        self.released = False
        self.stopped = False

    def __call__(self, *args: Any, **kwargs: Any) -> _FakeManager:
        return self

    async def acquire(self, options: Any = None) -> _FakePort:
        return _FakePort(self._headed)

    async def release(self, port: Any = None) -> None:
        self.released = True
        return None

    async def stop(self) -> None:
        self.stopped = True
        return None


class _Clock:
    """按次推进的假时钟：绕开 30s 超时下限，测试不真等。"""

    def __init__(self, step: float = 6.0) -> None:
        self._now = 0.0
        self._step = step

    def __call__(self) -> float:
        self._now += self._step
        return self._now


async def _recover(headed: _FakeHeaded, origin: _FakeOrigin) -> None:
    """在假浏览器 / 假时钟下跑一次 recover_risk。"""
    with (
        patch.object(recovery, "BrowserManager", _FakeManager(headed)),
        patch.object(recovery.asyncio, "sleep", AsyncMock()),
        patch.object(recovery.time, "monotonic", _Clock()),
    ):
        await recovery.XianyuRiskRecovery().recover_risk(
            origin,
            where="detail",
            url=_ITEM_URL,
        )


def test_manual_wait_keeps_waiting_until_content_renders() -> None:
    """页面没渲出正文就不能算通过 —— 旧实现 goto 后 1s 就返回了。"""

    async def _case() -> None:
        headed = _FakeHeaded(_FakeRaw(body=""))
        origin = _FakeOrigin()
        with pytest.raises(AppError) as raised:
            await _recover(headed, origin)

        assert raised.value.code == "channel.risk"
        # 真的在反复轮询等人，而不是第一轮就收工
        assert headed.polls > 1
        assert headed.closed is True
        assert origin.added == []

    asyncio.run(_case())


class _ClearingRaw(_FakeRaw):
    """先卡在风控页、随后切回商品页；正文始终很短（详情页常见）。

    切换靠读 URL 的次数而不是 evaluate：`page_is_risk_block` 命中 punish URL 时
    会直接返回，根本走不到取正文那一步。
    """

    def __init__(self) -> None:
        super().__init__(body="商品详情")
        self.url_reads = 0

    @property
    def url(self) -> str:
        self.url_reads += 1
        # 前几轮仍在风控页，之后用户过掉滑块、URL 回到商品页
        if self.url_reads <= 3:
            return "https://passport.goofish.com/_____tmd_____/punish"
        return _ITEM_URL


class _HangingHeaded(_FakeHeaded):
    """close() 卡死的有头窗口：用来验证关闭链路不会连带卡住。"""

    async def close(self) -> None:
        await asyncio.sleep(60)


def test_manual_wait_passes_once_risk_ui_clears() -> None:
    """见过风控后，风控 UI 消失即判过 —— 详情页正文常常不到 120 字。

    旧实现还要求「正文渲染 ≥120 字」，于是用户过完滑块程序仍在干等 180s，
    表现就是「窗口一直不关」。
    """

    async def _case() -> None:
        headed = _FakeHeaded(_ClearingRaw())
        origin = _FakeOrigin()
        await _recover(headed, origin)

        assert headed.closed is True
        assert [cookie.name for cookie in origin.added] == ["x5sec"]

    asyncio.run(_case())


def test_shutdown_keeps_going_when_close_hangs() -> None:
    """关页卡死也要继续走完还槽位 + 停池，否则窗口会留在用户桌面上。"""

    async def _case() -> None:
        headed = _HangingHeaded(_FakeRaw(body=""))
        manager = _FakeManager(headed)
        with patch.object(recovery, "_CLOSE_TIMEOUT_S", 0.05):
            await recovery._shutdown_headed(manager, None, headed, where="detail")

        # close 被 wait_for 掐断，但池必须被停掉
        assert manager.stopped is True

    asyncio.run(_case())


def test_manual_wait_passes_and_writes_cookies_back() -> None:
    """人工过完（正文渲染 + 风控 UI 消失）→ 判通过并把新 Cookie 写回原 page。"""

    async def _case() -> None:
        headed = _FakeHeaded(_FakeRaw(body="商品标题 " + "详情" * 200))
        origin = _FakeOrigin()
        await _recover(headed, origin)

        assert headed.closed is True
        # 不回写的话调用方拿原 context 重试还会撞同一张 punish 页
        assert [cookie.name for cookie in origin.added] == ["x5sec"]

    asyncio.run(_case())
