"""闲鱼 token 调度器测试。"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from src.domains.account.token_scheduler import (
    probe_all_xianyu_tokens,
    run_token_refresh_loop,
)


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


def test_probe_all_xianyu_uses_token_renew_not_bare_probe() -> None:
    """启动探活走 token（可静默续期），不直接 probe 判死。"""
    row = SimpleNamespace(
        account_id="xy-1",
        platform="xianyu",
        display_name="测",
        avatar_url=None,
        cookie="unb=1; _m_h5_tk=old; cookie2=c",
        status="active",
        auto_connect=True,
        connected=False,
    )
    with (
        patch(
            "src.domains.account.token_scheduler.account_repo.list_accounts",
            return_value=[row],
        ),
        patch(
            "src.domains.account.token_scheduler.token",
            return_value=("unb=1; _m_h5_tk=new; cookie2=c", True),
        ) as token_mock,
        patch(
            "src.domains.account.token_scheduler.account_repo.set_auth_valid",
        ) as set_valid,
        patch(
            "src.domains.account.token_scheduler.account_repo.upsert_account",
        ) as upsert,
    ):
        probe_all_xianyu_tokens()

    token_mock.assert_called_once_with(row.cookie)
    set_valid.assert_called_with("xy-1", True)
    upsert.assert_called_once()
    assert upsert.call_args.kwargs["cookie"].startswith("unb=1")
    assert upsert.call_args.kwargs["auth_valid"] is True


def test_probe_all_xianyu_marks_expired_only_when_renew_fails() -> None:
    row = SimpleNamespace(
        account_id="xy-2",
        platform="xianyu",
        display_name="测",
        avatar_url=None,
        cookie="unb=1; _m_h5_tk=old; cookie2=c",
        status="active",
        auto_connect=True,
        connected=False,
    )
    with (
        patch(
            "src.domains.account.token_scheduler.account_repo.list_accounts",
            return_value=[row],
        ),
        patch(
            "src.domains.account.token_scheduler.token",
            return_value=(row.cookie, False),
        ),
        patch(
            "src.domains.account.token_scheduler.account_repo.set_auth_valid",
        ) as set_valid,
        patch(
            "src.domains.account.token_scheduler.account_repo.upsert_account",
        ) as upsert,
    ):
        probe_all_xianyu_tokens()

    set_valid.assert_called_with("xy-2", False)
    upsert.assert_not_called()
