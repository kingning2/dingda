"""扫码/连接后补全账号昵称与头像。

职责：
    闲鱼用 ``user.page.nav`` 补昵称头像并写回 accounts 表。小红书在扫码成功时已写入，不再二次拉取。

设计说明：
    - 失败只打日志，不挡登录成功
    - 调用方：persist 后台线程、闲鱼 connect

使用示例：
    enrich_account_profile(account_id, platform="xianyu", cookie=cookie)
"""

from __future__ import annotations

import logging

from src.channels.xianyu.refresh import profile as xianyu_profile
from src.infrastructure.db import accounts as account_repo

logger = logging.getLogger("dingda.account.enrich")


def fetch_profile(platform: str, cookie: str) -> tuple[str | None, str | None]:
    if not cookie.strip():
        return None, None
    if platform == "xianyu":
        return xianyu_profile(cookie)
    return None, None


def enrich_account_profile(account_id: str, *, platform: str, cookie: str) -> bool:
    """拉取平台资料并写回 SQLite，返回是否有更新。"""
    display_name, avatar_url = fetch_profile(platform, cookie)
    if not display_name and not avatar_url:
        logger.debug("账号资料无更新: %s (%s)", account_id, platform)
        return False

    existing = account_repo.get_account(account_id)
    if not existing:
        logger.warning("账号不存在，跳过资料补全: %s", account_id)
        return False

    next_name = (display_name or existing.display_name).strip()
    next_avatar = avatar_url or existing.avatar_url
    if next_name == existing.display_name and next_avatar == existing.avatar_url:
        logger.debug("账号资料已是最新: %s", account_id)
        return False

    account_repo.upsert_account(
        account_id=existing.account_id,
        platform=existing.platform,
        display_name=next_name,
        avatar_url=next_avatar,
        cookie=existing.cookie,
        status=existing.status,
        auto_connect=existing.auto_connect,
        auth_valid=existing.auth_valid,
        connected=existing.connected,
    )
    logger.info(
        "账号资料已更新: %s name=%s avatar=%s",
        account_id,
        next_name,
        "yes" if next_avatar else "no",
    )
    return True


def enrich_account_profile_async(
    *,
    account_id: str,
    platform: str,
    cookie: str,
) -> None:
    import threading

    def _run() -> None:
        try:
            enrich_account_profile(account_id, platform=platform, cookie=cookie)
        except Exception as exc:
            logger.warning("后台资料补全失败 %s: %s", account_id, exc)

    threading.Thread(
        target=_run,
        name=f"enrich-{account_id}",
        daemon=True,
    ).start()
