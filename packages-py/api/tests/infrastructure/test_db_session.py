"""infrastructure.db 会话层测试：WAL pragma、事务语义、并发写。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from infrastructure.db.session import (
    connect,
    connection,
    db_path,
    set_db_path,
)


@pytest.fixture(autouse=True)
def _temp_db(tmp_path: Path) -> None:
    set_db_path(tmp_path / "session.db")
    yield
    set_db_path(None)


def test_connect_enables_wal(tmp_path: Path) -> None:
    conn = connect(tmp_path / "wal.db")
    try:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal"
        # busy_timeout 与 connect(timeout=...) 是同一把锁等待，读回的是毫秒
        busy = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        assert busy == 5000
    finally:
        conn.close()


def test_connection_commits_on_success() -> None:
    with connection() as conn:
        conn.execute("CREATE TABLE t (v TEXT)")
        conn.execute("INSERT INTO t VALUES ('ok')")

    check = connect(db_path())
    try:
        assert check.execute("SELECT v FROM t").fetchall()[0][0] == "ok"
    finally:
        check.close()


def test_connection_rolls_back_on_error() -> None:
    with connection() as conn:
        conn.execute("CREATE TABLE t (v TEXT UNIQUE)")

    with pytest.raises(sqlite3.IntegrityError), connection() as conn:
        conn.execute("INSERT INTO t VALUES ('a')")
        conn.execute("INSERT INTO t VALUES ('a')")

    check = connect(db_path())
    try:
        assert check.execute("SELECT count(*) FROM t").fetchone()[0] == 0
    finally:
        check.close()


def test_concurrent_writers_wait_instead_of_failing() -> None:
    """两连接交替写同一表：busy_timeout 生效时不抛 database is locked。"""
    with connection() as conn:
        conn.execute("CREATE TABLE t (v INTEGER)")

    writer_a = connect(db_path())
    writer_b = connect(db_path())
    try:
        for index in range(20):
            writer = writer_a if index % 2 == 0 else writer_b
            writer.execute("INSERT INTO t VALUES (?)", (index,))
            writer.commit()

        check = connect(db_path())
        try:
            assert check.execute("SELECT count(*) FROM t").fetchone()[0] == 20
        finally:
            check.close()
    finally:
        writer_a.close()
        writer_b.close()
