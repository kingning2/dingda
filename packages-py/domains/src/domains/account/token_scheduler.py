"""账号登录态探活与闲鱼 token 定时刷新（bootstrap 预热后启动）。

职责：
    启动时探活闲鱼 / 小红书 / 1688；闲鱼每 10 分钟再续 token。

设计说明：
    - 闲鱼启动探活对齐 goofish-cli：先 ``loginuser.get``，令牌/会话可恢复则
      浏览器静默续期（快速进入），续不上才标过期（才需要扫码）
    - 小红书探活对齐 xiaohongshu-mcp ``CheckLoginStatus``，不走同步扫码线程
    - 1688 只看账户对应 AK 是否还在本地/环境变量，不开浏览器
    - 由 warmup ``ensure_warmed`` 挂上，不挡 /health
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from channels.ali1688.ak import probe as probe_ali1688_ak
from channels.xianyu.refresh import token
from channels.xiaohongshu.status import probe as probe_xiaohongshu
from infrastructure.db import accounts as account_repo

logger = logging.getLogger("dingda.account.token_scheduler")

REFRESH_INTERVAL_SECONDS = 600

_scheduler_task: asyncio.Task[None] | None = None


def _apply_xianyu_token_result(row: Any, *, phase: str) -> None:
    """对单个闲鱼账号：ping → 必要时静默续期 → 写回 cookie / auth_valid。"""
    if not row.cookie.strip():
        account_repo.set_auth_valid(row.account_id, False)
        logger.info("闲鱼%s过期: %s（无 cookie）", phase, row.account_id)
        return

    new_cookie, ok = token(row.cookie)
    if not ok:
        account_repo.set_auth_valid(row.account_id, False)
        logger.info("闲鱼%s失败: %s valid=False（续期未恢复，需扫码）", phase, row.account_id)
        return

    account_repo.set_auth_valid(row.account_id, True)
    if new_cookie.strip() == row.cookie.strip():
        logger.info("闲鱼%s结果: %s valid=True cookie_unchanged=True", phase, row.account_id)
        return

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
    logger.info("闲鱼%s结果: %s valid=True cookie_updated=True", phase, row.account_id)


def probe_all_xianyu_tokens() -> None:
    """启动探活：HTTP ping，失败则浏览器静默续期，续不上才标过期。"""
    rows = account_repo.list_accounts(platform="xianyu")
    if not rows:
        logger.info("闲鱼登录态探活：无账号，跳过")
        return

    logger.info("闲鱼登录态探活（%s 个账号，可静默续期）", len(rows))
    for row in rows:
        _apply_xianyu_token_result(row, phase="探活")


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


def probe_all_ali1688() -> None:
    """1688 探活：账户 cookie 里的 AK 是否仍在本地/环境变量。"""
    rows = account_repo.list_accounts(platform="ali1688")
    if not rows:
        return

    logger.info("1688 AK 探活（%s 个账号）", len(rows))
    for row in rows:
        valid = probe_ali1688_ak(row.cookie)
        account_repo.set_auth_valid(row.account_id, valid)
        logger.info("1688 探活结果: %s valid=%s", row.account_id, valid)


def refresh_all_xianyu_tokens() -> None:
    """周期续期（与启动探活同一路径）。"""
    rows = account_repo.list_accounts(platform="xianyu")
    if not rows:
        logger.info("闲鱼 token 刷新：无账号，跳过")
        return

    logger.info("开始刷新闲鱼 token（%s 个账号）", len(rows))
    for row in rows:
        _apply_xianyu_token_result(row, phase="续期")


async def run_token_refresh_loop() -> None:
    logger.info(
        "闲鱼 token 周期调度已启动（每 %s 秒）",
        REFRESH_INTERVAL_SECONDS,
    )
    while True:
        await asyncio.sleep(REFRESH_INTERVAL_SECONDS)
        logger.info("闲鱼 token 周期到点，开始刷新")
        try:
            await asyncio.to_thread(refresh_all_xianyu_tokens)
        except Exception as exc:
            logger.warning("闲鱼 token 定时刷新异常: %s", exc)
        try:
            await asyncio.to_thread(probe_all_ali1688)
        except Exception as exc:
            logger.warning("1688 AK 定时探活异常: %s", exc)


def schedule_xianyu_token_scheduler() -> None:
    """在壳层 bootstrap 预热完成后启动（幂等，不阻塞首屏）。"""
    global _scheduler_task

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("闲鱼 token 调度未挂上：无 running event loop")
        return

    if _scheduler_task is not None and not _scheduler_task.done():
        logger.info("闲鱼 token 调度已在运行，跳过重复挂载")
        return

    async def _bootstrap_scheduler() -> None:
        logger.info("闲鱼 token 调度 bootstrap 开始（探活+静默续期 → 周期续期）")
        try:
            await asyncio.to_thread(probe_all_xianyu_tokens)
        except Exception as exc:
            logger.warning("闲鱼登录态探活异常: %s", exc)
        try:
            await probe_all_xiaohongshu()
        except Exception as exc:
            logger.warning("小红书登录态探活异常: %s", exc)
        try:
            await asyncio.to_thread(probe_all_ali1688)
        except Exception as exc:
            logger.warning("1688 AK 探活异常: %s", exc)
        await run_token_refresh_loop()

    _scheduler_task = loop.create_task(
        _bootstrap_scheduler(),
        name="xianyu-token-refresh",
    )
    logger.info("闲鱼 token 调度任务已创建")
