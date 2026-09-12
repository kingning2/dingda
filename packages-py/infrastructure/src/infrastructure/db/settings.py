"""应用偏好 KV（SQLite）。

职责：
    读写 ``app_settings`` 表；默认 Agent CLI id、各 Agent 默认模型、
    以及上次手动扫描的 Agent CLI 目录（含模型列表）。
    只做 SQL，不写 HTTP 文案。

设计说明：
    - 表结构在 ``schema.APP_SETTINGS_TABLE_SQL``
    - 调用方：``api.agent`` 偏好 / runtimes 接口
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Iterator

from infrastructure.db.schema import APP_SETTINGS_TABLE_SQL
from infrastructure.db.session import db_path

logger = logging.getLogger("dingda.db.settings")

DEFAULT_AGENT_KEY = "default_agent_id"
DEFAULT_MODELS_KEY = "default_models"
AGENT_RUNTIMES_KEY = "agent_runtimes_catalog"


def ensure_schema() -> None:
    """确保 app_settings 表存在。"""
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(APP_SETTINGS_TABLE_SQL)


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


def get_default_agent_id() -> str | None:
    """读取当前默认 Agent id。"""
    return get_setting(DEFAULT_AGENT_KEY)


def set_default_agent_id(agent_id: str) -> str:
    """写入默认 Agent id。"""
    return set_setting(DEFAULT_AGENT_KEY, agent_id)


def get_default_models() -> dict[str, str]:
    """读取各 Agent 的默认模型映射 ``{agent_id: model_id}``。"""
    raw = get_setting(DEFAULT_MODELS_KEY)
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("default_models JSON 无效，已重置为空")
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for key, value in data.items():
        agent_id = str(key).strip()
        model_id = str(value).strip() if value is not None else ""
        if agent_id and model_id:
            out[agent_id] = model_id
    return out


def set_default_model(agent_id: str, model_id: str) -> dict[str, str]:
    """写入某 Agent 的默认模型，返回完整映射。"""
    agent = agent_id.strip()
    model = model_id.strip()
    mapping = get_default_models()
    mapping[agent] = model
    set_setting(DEFAULT_MODELS_KEY, json.dumps(mapping, ensure_ascii=False, separators=(",", ":")))
    return mapping


def get_agent_runtimes_catalog() -> list[dict[str, Any]]:
    """读取上次扫描落库的 Agent CLI 目录（含模型）。"""
    raw = get_setting(AGENT_RUNTIMES_KEY)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("agent_runtimes_catalog JSON 无效，已重置为空")
        return []
    if not isinstance(data, list):
        return []
    out: list[dict[str, Any]] = []
    for item in data:
        if isinstance(item, dict) and str(item.get("id", "")).strip():
            out.append(item)
    return out


def set_agent_runtimes_catalog(agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """覆盖写入 Agent CLI 扫描结果。"""
    cleaned: list[dict[str, Any]] = []
    for item in agents:
        if not isinstance(item, dict):
            continue
        agent_id = str(item.get("id", "")).strip()
        if not agent_id:
            continue
        cleaned.append(item)
    set_setting(
        AGENT_RUNTIMES_KEY,
        json.dumps(cleaned, ensure_ascii=False, separators=(",", ":")),
    )
    logger.info("已保存 Agent 扫描目录 count=%s", len(cleaned))
    return cleaned
