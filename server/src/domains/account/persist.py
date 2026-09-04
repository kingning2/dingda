"""账号登录态落库（由 Python 侧在扫码成功时调用）。"""

from __future__ import annotations

import logging

from src.infrastructure.db import accounts as account_repo

logger = logging.getLogger("dingda.account.persist")


def save_login_credentials(
    *,
    platform: str,
    account_id: str | None,
    display_name: str | None,
    cookie: str | None,
    avatar_url: str | None = None,
) -> None:
    """扫码成功时写入 SQLite，保留已有 auto_connect 偏好。"""
    if not account_id or not cookie or not cookie.strip():
        return

    final_id = account_id
    final_name = (display_name or account_id).strip()
    final_cookie = cookie.strip()
    final_avatar = avatar_url.strip() if avatar_url and avatar_url.strip() else None

    existing = account_repo.get_account(final_id)
    if not final_avatar and existing:
        final_avatar = existing.avatar_url

    auto_connect = existing.auto_connect if existing else False
    connected = True if platform == "xianyu" else (existing.connected if existing else False)

    account_repo.upsert_account(
        account_id=final_id,
        platform=platform,
        display_name=final_name,
        avatar_url=final_avatar,
        cookie=final_cookie,
        auto_connect=auto_connect,
        auth_valid=True,
        connected=connected,
    )
    logger.info(
        "账号已写入 SQLite: %s (%s) connected=%s",
        final_id,
        platform,
        connected,
    )
