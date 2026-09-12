"""数据库基础设施包导出。

导出数据库路径解析与启停钩子，供 ``core.lifespan`` 调用。
"""

from infrastructure.db.session import db_path, init_db, shutdown_db

__all__ = ["db_path", "init_db", "shutdown_db"]
