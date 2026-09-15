"""闲鱼风控恢复：后台轮询模式不得弹有头窗口阻塞等人。"""

from __future__ import annotations

import asyncio
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from channels.xianyu.risk_recovery import (
    XianyuRiskRecovery,
    background_mode,
    in_background_mode,
)
from core.errors import AppError


def _page() -> SimpleNamespace:
    """够 recover_risk 走到「自动滑块失败」那一步的最小 page。"""
    return SimpleNamespace(
        raw=object(),
        context=object(),
        url="https://www.goofish.com/item?id=1",
        cookies=AsyncMock(return_value=[]),
        add_cookies=AsyncMock(),
    )


def _slider_fails() -> tuple[ExitStack, AsyncMock, AsyncMock]:
    """自动滑块必失败，并拦住人工窗口与 Cookie 导出；返回待断言的 mock。"""
    headed = AsyncMock(return_value=[])
    writeback = AsyncMock()
    stack = ExitStack()
    stack.enter_context(patch("channels.xianyu.risk_recovery.auto_slider_enabled", return_value=True))
    stack.enter_context(patch("channels.xianyu.risk_recovery.clear_risk_cookies", new=AsyncMock()))
    stack.enter_context(
        patch(
            "channels.xianyu.risk_recovery.try_solve_slider",
            new=AsyncMock(return_value=(False, "未通过")),
        )
    )
    stack.enter_context(
        patch(
            "channels.xianyu.risk_recovery._cookies_from_page",
            new=AsyncMock(return_value=[]),
        )
    )
    stack.enter_context(patch("channels.xianyu.risk_recovery._wait_manual_headed", new=headed))
    stack.enter_context(patch("channels.xianyu.risk_recovery._write_back_cookies", new=writeback))
    return stack, headed, writeback


def test_background_mode_flag_is_scoped_to_context() -> None:
    assert in_background_mode() is False
    with background_mode():
        assert in_background_mode() is True
    assert in_background_mode() is False


def test_background_mode_raises_instead_of_opening_headed_window() -> None:
    """后台轮询撞风控：只走自动滑块，失败直接 channel.risk，不弹窗等人。"""
    recovery = XianyuRiskRecovery()
    stack, headed, writeback = _slider_fails()

    with stack, background_mode():
        with pytest.raises(AppError) as excinfo:
            asyncio.run(recovery.recover_risk(_page(), where="detail"))

    assert excinfo.value.code == "channel.risk"
    headed.assert_not_called()
    writeback.assert_not_called()


def test_foreground_still_opens_manual_window() -> None:
    """前台抓取不受影响：自动滑块失败后仍要开有头窗口等人。"""
    recovery = XianyuRiskRecovery()
    stack, headed, writeback = _slider_fails()

    with stack:
        asyncio.run(recovery.recover_risk(_page(), where="detail"))

    headed.assert_awaited_once()
    writeback.assert_awaited_once()


def test_background_mode_returns_early_when_auto_slider_succeeds() -> None:
    """自动滑块过了就不该判失败，后台模式也一样。"""
    recovery = XianyuRiskRecovery()
    with (
        patch("channels.xianyu.risk_recovery.auto_slider_enabled", return_value=True),
        patch("channels.xianyu.risk_recovery.clear_risk_cookies", new=AsyncMock()),
        patch(
            "channels.xianyu.risk_recovery.try_solve_slider",
            new=AsyncMock(return_value=(True, "通过")),
        ),
        patch(
            "channels.xianyu.risk_recovery._wait_manual_headed",
            new=AsyncMock(return_value=[]),
        ) as headed,
    ):
        with background_mode():
            asyncio.run(recovery.recover_risk(_page(), where="detail"))

    headed.assert_not_called()
