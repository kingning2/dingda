"""账号登录态落库（由 Python 侧在扫码成功时调用）。"""

from __future__ import annotations

import logging

from src.channels.cookie_header import parse_cookie_header
from src.infrastructure.db import accounts as account_repo

logger = logging.getLogger("dingda.account.persist")


def save_login_credentials(
    *,
    platform: str,
    account_id: str | None,
    display_name: str | None,
    cookie: str | None,
    avatar_url: str | None = None,
    local_storage: dict[str, str] | None = None,
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
        local_storage=local_storage,
    )
    logger.info(
        "账号已写入 SQLite: %s (%s) connected=%s ls_keys=%s",
        final_id,
        platform,
        connected,
        len(local_storage or {}),
    )
    if platform == "xiaohongshu":
        _cleanup_xhs_session_orphans(final_id, final_cookie)


def _is_xhs_session_fallback_id(account_id: str) -> bool:
    """``xhs:`` + web_session 前 12 位；真 user_id 更长。"""
    if not account_id.startswith("xhs:"):
        return False
    return len(account_id) == len("xhs:") + 12


def _cleanup_xhs_session_orphans(keep_id: str, cookie: str) -> None:
    """同一 a1 下清理历史「web_session 假 id」卡片，避免重复扫码堆卡片。"""
    parsed = parse_cookie_header(cookie)
    a1 = (parsed.get("a1") or "").strip()
    if not a1:
        return
    for row in account_repo.list_accounts(platform="xiaohongshu"):
        if row.account_id == keep_id:
            continue
        if not _is_xhs_session_fallback_id(row.account_id):
            continue
        if a1 not in (row.cookie or ""):
            continue
        if account_repo.delete_account(row.account_id):
            logger.info(
                "已清理小红书重复假账号 orphan=%s keep=%s",
                row.account_id,
                keep_id,
            )
