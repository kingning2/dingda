"""SQLite 表结构定义。"""

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
