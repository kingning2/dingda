"""账号 SQLite 读写（dingda 自有层，不依赖第三方 vendor）。"""

from __future__ import annotations

import sqlite3
import json
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from infrastructure.db.schema import (
    ACCOUNTS_AUTH_VALID_COLUMN_SQL,
    ACCOUNTS_AVATAR_COLUMN_SQL,
    ACCOUNTS_CONNECTED_COLUMN_SQL,
    ACCOUNTS_LOCAL_STORAGE_COLUMN_SQL,
    ACCOUNTS_TABLE_SQL,
)
from infrastructure.db.session import db_path


@dataclass(frozen=True, slots=True)
class AccountRow:
    account_id: str
    platform: str
    display_name: str
    avatar_url: str | None
    cookie: str
    local_storage: str
    status: str
    auto_connect: bool
    auth_valid: bool
    connected: bool
    created_at: float
    updated_at: float


def ensure_schema() -> None:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(ACCOUNTS_TABLE_SQL)
        try:
            conn.execute(ACCOUNTS_AVATAR_COLUMN_SQL)
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute(ACCOUNTS_AUTH_VALID_COLUMN_SQL)
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute(ACCOUNTS_CONNECTED_COLUMN_SQL)
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute(ACCOUNTS_LOCAL_STORAGE_COLUMN_SQL)
        except sqlite3.OperationalError:
            pass


@contextmanager
def _connection() -> Iterator[sqlite3.Connection]:
    ensure_schema()
    conn = sqlite3.connect(db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _row_to_account(row: sqlite3.Row) -> AccountRow:
    return AccountRow(
        account_id=str(row["account_id"]),
        platform=str(row["platform"]),
        display_name=str(row["display_name"]),
        avatar_url=str(row["avatar_url"]) if row["avatar_url"] else None,
        cookie=str(row["cookie"]),
        local_storage=str(row["local_storage"])
        if "local_storage" in row.keys() and row["local_storage"] is not None
        else "{}",
        status=str(row["status"]),
        auto_connect=bool(row["auto_connect"]),
        auth_valid=bool(row["auth_valid"]) if "auth_valid" in row.keys() else True,
        connected=bool(row["connected"]) if "connected" in row.keys() else False,
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
    )


def list_accounts(*, platform: str | None = None) -> list[AccountRow]:
    with _connection() as conn:
        if platform:
            rows = conn.execute(
                "SELECT * FROM accounts WHERE platform = ? ORDER BY updated_at DESC",
                (platform,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM accounts ORDER BY updated_at DESC",
            ).fetchall()
    return [_row_to_account(row) for row in rows]


def get_account(account_id: str) -> AccountRow | None:
    with _connection() as conn:
        row = conn.execute(
            "SELECT * FROM accounts WHERE account_id = ?",
            (account_id,),
        ).fetchone()
    return _row_to_account(row) if row else None


def upsert_account(
    *,
    account_id: str,
    platform: str,
    display_name: str,
    cookie: str,
    avatar_url: str | None = None,
    status: str = "active",
    auto_connect: bool = False,
    auth_valid: bool | None = None,
    connected: bool | None = None,
    local_storage: str | dict[str, str] | None = None,
) -> AccountRow:
    now = time.time()
    existing = get_account(account_id)
    resolved_avatar = avatar_url if avatar_url is not None else (
        existing.avatar_url if existing else None
    )
    resolved_auth_valid = (
        auth_valid
        if auth_valid is not None
        else (existing.auth_valid if existing else True)
    )
    resolved_connected = (
        connected
        if connected is not None
        else (existing.connected if existing else False)
    )
    if isinstance(local_storage, dict):
        resolved_local_storage = json.dumps(local_storage, ensure_ascii=False)
    elif local_storage is not None:
        resolved_local_storage = str(local_storage)
    else:
        resolved_local_storage = existing.local_storage if existing else "{}"
    with _connection() as conn:
        if existing:
            conn.execute(
                """
                UPDATE accounts
                SET platform = ?, display_name = ?, avatar_url = ?, cookie = ?,
                    local_storage = ?, status = ?,
                    auto_connect = ?, auth_valid = ?, connected = ?, updated_at = ?
                WHERE account_id = ?
                """,
                (
                    platform,
                    display_name,
                    resolved_avatar,
                    cookie,
                    resolved_local_storage,
                    status,
                    int(auto_connect),
                    int(resolved_auth_valid),
                    int(resolved_connected),
                    now,
                    account_id,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO accounts (
                    account_id, platform, display_name, avatar_url, cookie, local_storage,
                    status, auto_connect, auth_valid, connected, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    account_id,
                    platform,
                    display_name,
                    resolved_avatar,
                    cookie,
                    resolved_local_storage,
                    status,
                    int(auto_connect),
                    int(resolved_auth_valid),
                    int(resolved_connected),
                    now,
                    now,
                ),
            )
    saved = get_account(account_id)
    if not saved:
        raise RuntimeError(f"账号写入失败：{account_id}")
    return saved


def set_connected(account_id: str, connected: bool) -> None:
    now = time.time()
    with _connection() as conn:
        conn.execute(
            "UPDATE accounts SET connected = ?, updated_at = ? WHERE account_id = ?",
            (int(connected), now, account_id),
        )


def set_auth_valid(account_id: str, auth_valid: bool) -> None:
    now = time.time()
    with _connection() as conn:
        conn.execute(
            "UPDATE accounts SET auth_valid = ?, updated_at = ? WHERE account_id = ?",
            (int(auth_valid), now, account_id),
        )


def delete_account(account_id: str) -> bool:
    with _connection() as conn:
        cursor = conn.execute(
            "DELETE FROM accounts WHERE account_id = ?",
            (account_id,),
        )
    return cursor.rowcount > 0
