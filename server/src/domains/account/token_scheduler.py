"""账号登录态探活与闲鱼 token 定时刷新（bootstrap 预热后启动）。

职责：
    启动时探活闲鱼（HTTP）与小红书（异步 BrowserPool 开探索页）；闲鱼每 10 分钟再续 token。

设计说明：
    - 小红书探活对齐 xiaohongshu-mcp ``CheckLoginStatus``，不走同步扫码线程
    - 由 warmup ``ensure_warmed`` 挂上，不挡 /health
"""

from __future__ import annotations

import asyncio
import logging

from src.channels.xianyu.refresh import probe, token
from src.channels.xiaohongshu.status import probe as probe_xiaohongshu
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
        account_repo.set_auth_valid(row.account_id, probe(row.cookie))


async def probe_all_xiaohongshu() -> None:
    """启动时探活小红书登录态（异步开探索页看侧栏）。"""
    rows = account_repo.list_accounts(platform="xiaohongshu")
    if not rows:
        return

    logger.info("小红书登录态探活（%s 个账号）", len(rows))
    for row in rows:
        if not row.cookie.strip():
            account_repo.set_auth_valid(row.account_id, False)
            logger.info("小红书探活过期: %s（无 cookie）", row.account_id)
            continue
        valid = await probe_xiaohongshu(row.cookie)
        account_repo.set_auth_valid(row.account_id, valid)
        logger.info("小红书探活结果: %s valid=%s", row.account_id, valid)


def refresh_all_xianyu_tokens() -> None:
    rows = account_repo.list_accounts(platform="xianyu")
    if not rows:
        return

    logger.info("开始刷新闲鱼 token（%s 个账号）", len(rows))
    for row in rows:
        if not row.cookie.strip():
            continue
        new_cookie, ok = token(row.cookie)
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
        try:
            await probe_all_xiaohongshu()
        except Exception as exc:
            logger.warning("小红书登录态探活异常: %s", exc)
        await run_token_refresh_loop()

    _scheduler_task = loop.create_task(
        _bootstrap_scheduler(),
        name="xianyu-token-refresh",
    )
