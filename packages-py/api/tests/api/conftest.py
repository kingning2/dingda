"""API 测试公共 fixture。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _disable_xianyu_token_scheduler() -> None:
    with patch(
        "api.boot.warmup.schedule_xianyu_token_scheduler",
        new=MagicMock(),
    ):
        yield


@pytest.fixture(autouse=True)
def _disable_watch_scheduler() -> None:
    """禁止测试真的挂上监控轮询调度。

    ``/v1/bootstrap`` 会走 ``ensure_warmed``，若不拦住，测试进程会开始对
    真实闲鱼账号发起轮询。
    """
    with patch(
        "api.boot.warmup.schedule_watch_scheduler",
        new=MagicMock(),
    ):
        yield
