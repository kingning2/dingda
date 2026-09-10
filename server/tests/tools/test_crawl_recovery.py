"""Tool 层抓取恢复：登录失效 → 扫码 → 重试（不启浏览器 / 不真扫码）。"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

from src.shared.errors import AppError, session_expired_error
from src.tools import recovery as recovery_mod


def test_with_crawl_recovery_relogin_and_retry() -> None:
    async def _run() -> None:
        calls = {"n": 0}

        async def _body(cookie: str | None) -> str:
            calls["n"] += 1
            if calls["n"] == 1:
                raise session_expired_error("xianyu")
            return f"ok:{cookie}"

        with (
            patch.object(
                recovery_mod,
                "resolve_crawl_cookie",
                side_effect=["old-cookie", "fresh-cookie"],
            ) as resolve,
            patch.object(
                recovery_mod,
                "run_login",
                new_callable=AsyncMock,
                return_value=SimpleNamespace(ok=True, account_id="a1", error_code=None, message=None),
            ) as login,
        ):
            out = await recovery_mod.with_crawl_recovery("xianyu", _body)

        assert out == "ok:fresh-cookie"
        assert calls["n"] == 2
        assert login.await_count == 1
        assert resolve.call_count >= 2

    asyncio.run(_run())


def test_with_crawl_recovery_gives_up_after_max_auth() -> None:
    async def _run() -> None:
        async def _body(cookie: str | None) -> str:
            raise session_expired_error("xiaohongshu")

        with (
            patch.object(recovery_mod, "resolve_crawl_cookie", return_value="c"),
            patch.object(
                recovery_mod,
                "run_login",
                new_callable=AsyncMock,
                return_value=SimpleNamespace(ok=True, account_id="a", error_code=None, message=None),
            ) as login,
        ):
            try:
                await recovery_mod.with_crawl_recovery(
                    "xiaohongshu", _body, max_auth=2
                )
            except AppError as exc:
                assert exc.code == "account.session_expired"
            else:  # pragma: no cover - 应抛异常
                raise AssertionError("预期抛 session_expired")
        assert login.await_count == 2

    asyncio.run(_run())


def test_with_crawl_recovery_skips_login_for_unsupported_platform() -> None:
    async def _run() -> None:
        async def _body(cookie: str | None) -> str:
            raise session_expired_error("ali1688")

        with (
            patch.object(recovery_mod, "resolve_crawl_cookie", return_value=None),
            patch.object(
                recovery_mod, "run_login", new_callable=AsyncMock
            ) as login,
        ):
            try:
                await recovery_mod.with_crawl_recovery("ali1688", _body)
            except AppError as exc:
                assert exc.code == "account.session_expired"
            else:  # pragma: no cover
                raise AssertionError("预期抛 session_expired")
        assert login.await_count == 0

    asyncio.run(_run())
