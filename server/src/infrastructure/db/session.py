"""SQLite 数据库会话与路径管理。"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger("dingda.db")

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
    from src.infrastructure.db import accounts as account_repo
    from src.infrastructure.db import agent_works as agent_works_repo
    from src.infrastructure.db import settings as settings_repo

    account_repo.ensure_schema()
    settings_repo.ensure_schema()
    agent_works_repo.ensure_schema()
    logger.info("database ready: %s", db_path())


async def shutdown_db() -> None:
    logger.debug("database shutdown")
