"""闲鱼账号 token 定时刷新（bootstrap 预热后启动，默认每 10 分钟）。"""

from __future__ import annotations

import asyncio
import logging

from src.channels.xianyu.token_refresh import probe_token, refresh_token
from src.infrastructure.db import accounts as account_repo

logger = logging.getLogger("dingda.account.token_scheduler")

REFRESH_INTERVAL_SECONDS = 600

_scheduler_task: asyncio.Task[None] | None = None


def probe_all_xianyu_tokens() -> None:
    """HTTP 探活并更新 auth_valid，不启动 Camoufox。"""
    rows = account_repo.list_accounts(platform="xianyu")
    if not rows:
        return

    logger.info("闲鱼登录态探活（%s 个账号）", len(rows))
    for row in rows:
        if not row.cookie.strip():
            account_repo.set_auth_valid(row.account_id, False)
            continue
        account_repo.set_auth_valid(row.account_id, probe_token(row.cookie))


def refresh_all_xianyu_tokens() -> None:
    rows = account_repo.list_accounts(platform="xianyu")
    if not rows:
        return

    logger.info("开始刷新闲鱼 token（%s 个账号）", len(rows))
    for row in rows:
        if not row.cookie.strip():
            continue
        new_cookie, ok = refresh_token(row.cookie)
        if not ok:
            account_repo.set_auth_valid(row.account_id, False)
            continue
        account_repo.set_auth_valid(row.account_id, True)
        if new_cookie.strip() == row.cookie.strip():
            continue
        account_repo.upsert_account(
            account_id=row.account_id,
            platform=row.platform,
            display_name=row.display_name,
            avatar_url=row.avatar_url,
            cookie=new_cookie,
            status=row.status,
            auto_connect=row.auto_connect,
            auth_valid=True,
            connected=row.connected,
        )


async def run_token_refresh_loop() -> None:
    while True:
        await asyncio.sleep(REFRESH_INTERVAL_SECONDS)
        try:
            await asyncio.to_thread(refresh_all_xianyu_tokens)
        except Exception as exc:
            logger.warning("闲鱼 token 定时刷新异常: %s", exc)


def schedule_xianyu_token_scheduler() -> None:
    """在壳层 bootstrap 预热完成后启动（幂等，不阻塞首屏）。"""
    global _scheduler_task

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return

    if _scheduler_task is not None and not _scheduler_task.done():
        return

    async def _bootstrap_scheduler() -> None:
        try:
            await asyncio.to_thread(probe_all_xianyu_tokens)
        except Exception as exc:
            logger.warning("闲鱼登录态探活异常: %s", exc)
        await run_token_refresh_loop()

    _scheduler_task = loop.create_task(
        _bootstrap_scheduler(),
        name="xianyu-token-refresh",
    )
