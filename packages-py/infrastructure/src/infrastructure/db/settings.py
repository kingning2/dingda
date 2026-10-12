"""应用偏好 KV（SQLite）。

职责：
    读写 ``app_settings`` 表。只做 SQL，不写 HTTP 文案。

设计说明：
    - 表结构在 ``schema.APP_SETTINGS_TABLE_SQL``
"""

from __future__ import annotations

import logging
import sqlite3
import time
from contextlib import contextmanager
from typing import Iterator

from infrastructure.db.schema import APP_SETTINGS_TABLE_SQL
from infrastructure.db.session import connection, connect, db_path

logger = logging.getLogger("dingda.db.settings")


def ensure_schema() -> None:
    """确保 app_settings 表存在。"""
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as conn:
        conn.executescript(APP_SETTINGS_TABLE_SQL)


@contextmanager
def _connection() -> Iterator[sqlite3.Connection]:
    ensure_schema()
    with connection() as conn:
        yield conn


def get_setting(key: str) -> str | None:
    """按 key 读偏好；不存在返回 None。"""
    with _connection() as conn:
        row = conn.execute(
            "SELECT value FROM app_settings WHERE key = ?",
            (key,),
        ).fetchone()
    if not row:
        return None
    value = str(row["value"]).strip()
    return value or None


def set_setting(key: str, value: str) -> str:
    """写入偏好并返回规范化后的 value。"""
    normalized = value.strip()
    now = time.time()
    with _connection() as conn:
        conn.execute(
            """
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = excluded.updated_at
            """,
            (key, normalized, now),
        )
    return normalized
