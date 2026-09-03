"""API 测试公共 fixture。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _disable_xianyu_token_scheduler() -> None:
    with patch(
        "src.core.warmup.schedule_xianyu_token_scheduler",
        new=MagicMock(),
    ):
        yield
