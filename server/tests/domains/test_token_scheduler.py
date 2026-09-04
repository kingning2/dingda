"""闲鱼 token 调度器测试。"""

from __future__ import annotations

import asyncio
from unittest.mock import patch

from src.domains.account.token_scheduler import run_token_refresh_loop


def test_token_refresh_loop_waits_before_first_refresh() -> None:
    async def _run() -> None:
        with (
            patch(
                "src.domains.account.token_scheduler.REFRESH_INTERVAL_SECONDS",
                0.05,
            ),
            patch(
                "src.domains.account.token_scheduler.refresh_all_xianyu_tokens",
            ) as refresh_mock,
        ):
            task = asyncio.create_task(run_token_refresh_loop())
            await asyncio.sleep(0.01)
            refresh_mock.assert_not_called()
            await asyncio.sleep(0.08)
            refresh_mock.assert_called_once()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    asyncio.run(_run())
