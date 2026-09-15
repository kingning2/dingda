"""SQLite 表结构定义。

职责：
    以 SQL 常量集中声明全部产品表：账号、应用设置、AI 工作快照、商品监控。
    改表先改这里，再改 ``infrastructure.db`` 下对应的 repo 模块。

设计说明：
    - 只写 ``CREATE TABLE IF NOT EXISTS`` 与 ``ALTER TABLE``；不做迁移编排
    - accounts 的补列用独立常量，由 ``accounts.ensure_schema`` 逐个 try 执行
"""

from __future__ import annotations

ACCOUNTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS accounts (
    account_id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    display_name TEXT NOT NULL,
    cookie TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    auto_connect INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_accounts_platform ON accounts(platform);
"""

ACCOUNTS_AVATAR_COLUMN_SQL = """
ALTER TABLE accounts ADD COLUMN avatar_url TEXT;
"""

ACCOUNTS_AUTH_VALID_COLUMN_SQL = """
ALTER TABLE accounts ADD COLUMN auth_valid INTEGER NOT NULL DEFAULT 1;
"""

ACCOUNTS_CONNECTED_COLUMN_SQL = """
ALTER TABLE accounts ADD COLUMN connected INTEGER NOT NULL DEFAULT 0;
"""

ACCOUNTS_LOCAL_STORAGE_COLUMN_SQL = """
ALTER TABLE accounts ADD COLUMN local_storage TEXT NOT NULL DEFAULT '{}';
"""

APP_SETTINGS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL
);
"""

AGENT_WORKS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS agent_works (
    work_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    detail_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agent_works_updated ON agent_works(updated_at DESC);
"""

WATCH_TARGETS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS watch_targets (
    target_id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,
    item_id TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    url TEXT NOT NULL DEFAULT '',
    image_url TEXT,
    account_id TEXT,
    state TEXT NOT NULL DEFAULT 'active',
    sold_state TEXT NOT NULL DEFAULT 'unknown',
    first_price REAL,
    last_price REAL,
    min_price REAL,
    max_price REAL,
    last_want_count TEXT,
    last_status_text TEXT,
    poll_interval_seconds INTEGER NOT NULL,
    next_poll_at REAL NOT NULL,
    last_poll_at REAL,
    last_error TEXT,
    fail_count INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    UNIQUE(platform, item_id)
);
CREATE INDEX IF NOT EXISTS idx_watch_targets_due ON watch_targets(state, next_poll_at);
"""

WATCH_POINTS_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS watch_points (
    point_id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id TEXT NOT NULL,
    price REAL,
    price_text TEXT,
    want_count TEXT,
    browse_count TEXT,
    status_text TEXT,
    sold_state TEXT NOT NULL,
    observed_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_watch_points_target ON watch_points(target_id, observed_at DESC);
"""
