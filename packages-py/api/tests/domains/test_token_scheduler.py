"""闲鱼 token 调度器测试。"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

from domains.account.token_scheduler import (
    probe_all_ali1688,
    probe_all_xianyu_tokens,
    run_token_refresh_loop,
)


def test_token_refresh_loop_waits_before_first_refresh() -> None:
    async def _run() -> None:
        with (
            patch(
                "domains.account.token_scheduler.REFRESH_INTERVAL_SECONDS",
                0.05,
            ),
            patch(
                "domains.account.token_scheduler.refresh_all_xianyu_tokens",
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
            "domains.account.token_scheduler.account_repo.list_accounts",
            return_value=[row],
        ),
        patch(
            "domains.account.token_scheduler.token",
            return_value=("unb=1; _m_h5_tk=new; cookie2=c", True),
        ) as token_mock,
        patch(
            "domains.account.token_scheduler.account_repo.set_auth_valid",
        ) as set_valid,
        patch(
            "domains.account.token_scheduler.account_repo.upsert_account",
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
            "domains.account.token_scheduler.account_repo.list_accounts",
            return_value=[row],
        ),
        patch(
            "domains.account.token_scheduler.token",
            return_value=(row.cookie, False),
        ),
        patch(
            "domains.account.token_scheduler.account_repo.set_auth_valid",
        ) as set_valid,
        patch(
            "domains.account.token_scheduler.account_repo.upsert_account",
        ) as upsert,
    ):
        probe_all_xianyu_tokens()

    set_valid.assert_called_with("xy-2", False)
    upsert.assert_not_called()


def _ali1688_row(account_id: str = "ali1688:1") -> SimpleNamespace:
    return SimpleNamespace(
        account_id=account_id,
        platform="ali1688",
        display_name="1688 AK",
        avatar_url=None,
        cookie="stored-ak",
        status="active",
        auto_connect=True,
        connected=False,
    )


def _run_probe_all_ali1688(verdict: bool | None) -> tuple[list, list]:
    """跑一次 1688 定时探活，返回 (probe 的入参, set_auth_valid 的调用)。"""
    with (
        patch(
            "domains.account.token_scheduler.account_repo.list_accounts",
            return_value=[_ali1688_row()],
        ),
        patch(
            "domains.account.token_scheduler.probe_ali1688_account",
            return_value=verdict,
        ) as probe_mock,
        patch(
            "domains.account.token_scheduler.account_repo.set_auth_valid",
        ) as set_valid,
    ):
        probe_all_ali1688()

    return probe_mock.call_args_list, set_valid.call_args_list


def test_probe_all_ali1688_marks_expired_when_gateway_rejects() -> None:
    """【回归】账户存的 AK 本地还对得上、网关却拒了 —— 定时探活必须翻它。

    这正是这次修的洞：只看本地字符串的话，AK 被网关吊销或过期时账户页一直显示
    「已登录」，一调就错。定时探活是启动路径上唯一会碰 1688 的地方，
    它要还是只比字符串，这条修复就只在用户点开账号页之后才生效。
    """
    probes, writes = _run_probe_all_ali1688(False)

    assert [call.args for call in probes] == [("stored-ak",)], "要拿账户里存的那把 AK 去问"
    assert [call.args for call in writes] == [("ali1688:1", False)]


def test_probe_all_ali1688_recovers_to_valid() -> None:
    """网关认了就把「过期」收回来 —— 续了 AK 不必重启。"""
    _, writes = _run_probe_all_ali1688(True)

    assert [call.args for call in writes] == [("ali1688:1", True)]


def test_probe_all_ali1688_keeps_state_when_probe_cannot_tell() -> None:
    """「没问到」不写库 —— 一次网络抖动不该把用户打成「请重新扫码」。

    与 ``AccountService._sync_ali1688_auth`` 是同一条判据。两边不一致的话，
    列表刚写「过期」、10 分钟后调度又写「已登录」，前端就会来回翻。
    """
    probes, writes = _run_probe_all_ali1688(None)

    assert len(probes) == 1, "该问还是要问，只是别拿结论去写库"
    assert writes == []
