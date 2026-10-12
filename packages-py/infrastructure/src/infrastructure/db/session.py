"""SQLite 数据库会话与路径管理。"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

logger = logging.getLogger("dingda.db")

# 并发安全三件套：WAL（读写不互斥）+ busy_timeout（锁冲突等 5s 而非立即
# 抛 database is locked）+ synchronous=NORMAL（WAL 下安全且快）
BUSY_TIMEOUT_SECONDS = 5.0

_db_path: Path | None = None


def data_dir() -> Path:
    return Path.home() / ".dingda" / "v2"


def db_path() -> Path:
    global _db_path
    if _db_path is None:
        _db_path = data_dir() / "dingda.db"
    return _db_path


def set_db_path(path: Path | None) -> None:
    """测试或自定义数据目录时覆盖默认库路径。"""
    global _db_path
    _db_path = path


async def init_db() -> None:
    from infrastructure.db import accounts as account_repo
    from infrastructure.db import agent_works as agent_works_repo
    from infrastructure.db import settings as settings_repo
    from infrastructure.db import watch as watch_repo

    account_repo.ensure_schema()
    settings_repo.ensure_schema()
    agent_works_repo.ensure_schema()
    watch_repo.ensure_schema()
    logger.info("database ready: %s", db_path())


async def shutdown_db() -> None:
    logger.debug("database shutdown")


def connect(path: Path) -> sqlite3.Connection:
    """建连接的唯一出口：全项目 SQLite 必须从这里走，保证 WAL 与锁等待全局一致。"""
    conn = sqlite3.connect(
        path, check_same_thread=False, timeout=BUSY_TIMEOUT_SECONDS
    )
    conn.row_factory = sqlite3.Row
    # journal_mode 是库级持久属性，重复设置幂等；synchronous 是连接级的，逐连接设
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    """默认库连接的事务上下文：成功提交，异常回滚，退出必关。"""
    conn = connect(db_path())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
