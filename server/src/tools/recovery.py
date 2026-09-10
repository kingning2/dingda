"""选品 Tool：抓取会话恢复（登录失效→扫码→重试）。

职责：
    包装 search/product 执行体：捕获 ``account.session_expired`` /
    ``account.cookie_required``，调用 ``run_login`` 阻塞等扫码，
    成功后刷新 cookie 并重试同一任务。

设计说明：
    - 不碰 Playwright；扫码走 channels via tools.login
    - 同一调用最多恢复 ``max_auth`` 次
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from src.crawler.account_cookie import resolve_crawl_cookie
from src.shared.errors import AppError
from src.tools.login import LoginInput, run_login

logger = logging.getLogger("dingda.tools.recovery")

T = TypeVar("T")

_AUTH_CODES = frozenset({"account.session_expired", "account.cookie_required"})


async def with_crawl_recovery(
    platform: str,
    run: Callable[[str | None], Awaitable[T]],
    *,
    cookie: str | None = None,
    on_live_frame: Any | None = None,
    max_auth: int = 2,
) -> T:
    """执行 ``run(cookie)``；登录类错误则扫码后重试。"""
    plat = platform.strip().lower()
    current = resolve_crawl_cookie(plat, cookie)
    auth_tries = 0
    while True:
        try:
            return await run(current)
        except AppError as exc:
            if exc.code not in _AUTH_CODES or auth_tries >= max_auth:
                raise
            if plat not in {"xianyu", "xiaohongshu"}:
                raise
            auth_tries += 1
            logger.info(
                "crawl recovery login start platform=%s try=%s/%s code=%s",
                plat,
                auth_tries,
                max_auth,
                exc.code,
            )
            out = await run_login(LoginInput(platform=plat), on_live_frame=on_live_frame)
            if not out.ok:
                raise AppError(
                    out.error_code or "login.failed",
                    out.message or f"{plat}扫码登录失败",
                    status_code=401,
                )
            current = resolve_crawl_cookie(plat, None)
            if not current:
                raise AppError(
                    "account.session_expired",
                    f"{plat}扫码成功但账号库仍无 cookie",
                    status_code=401,
                )
            logger.info(
                "crawl recovery login ok platform=%s account=%s retry",
                plat,
                out.account_id,
            )
