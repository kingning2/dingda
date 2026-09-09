"""AI 工作对话快照（SQLite）。

职责：
    读写 ``agent_works`` 表：整份 ``AgentWorkDetailView`` JSON。
    产品侧自建对话真相源（对齐 OpenDesign conversations/messages 思路的简化版）。

设计说明：
    - 不解析外部 CLI 历史文件；只存叮答自己的快照
    - 调用方：``api.agent`` works 接口
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from src.infrastructure.db.schema import AGENT_WORKS_TABLE_SQL
from src.infrastructure.db.session import db_path

logger = logging.getLogger("dingda.db.agent_works")


@dataclass(frozen=True, slots=True)
class AgentWorkRow:
    work_id: str
    title: str
    detail: dict[str, Any]
    created_at: float
    updated_at: float


def ensure_schema() -> None:
    """确保 agent_works 表存在。"""
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(AGENT_WORKS_TABLE_SQL)


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


def get_work(work_id: str) -> AgentWorkRow | None:
    """按 work_id 读对话快照。"""
    key = work_id.strip()
    if not key:
        return None
    with _connection() as conn:
        row = conn.execute(
            "SELECT work_id, title, detail_json, created_at, updated_at FROM agent_works WHERE work_id = ?",
            (key,),
        ).fetchone()
    if not row:
        return None
    try:
        detail = json.loads(str(row["detail_json"]))
    except json.JSONDecodeError:
        logger.warning("agent_works detail_json invalid work_id=%s", key)
        return None
    if not isinstance(detail, dict):
        return None
    return AgentWorkRow(
        work_id=str(row["work_id"]),
        title=str(row["title"]),
        detail=detail,
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
    )


def list_works(*, limit: int = 40) -> list[AgentWorkRow]:
    """按更新时间倒序列出工作快照（不含完整 detail，只带摘要字段）。"""
    cap = max(1, min(int(limit), 100))
    with _connection() as conn:
        rows = conn.execute(
            """
            SELECT work_id, title, detail_json, created_at, updated_at
            FROM agent_works
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (cap,),
        ).fetchall()

    out: list[AgentWorkRow] = []
    for row in rows:
        try:
            detail = json.loads(str(row["detail_json"]))
        except json.JSONDecodeError:
            logger.warning("agent_works detail_json invalid work_id=%s", row["work_id"])
            continue
        if not isinstance(detail, dict):
            continue
        out.append(
            AgentWorkRow(
                work_id=str(row["work_id"]),
                title=str(row["title"]),
                detail=detail,
                created_at=float(row["created_at"]),
                updated_at=float(row["updated_at"]),
            )
        )
    return out


def upsert_work(work_id: str, detail: dict[str, Any]) -> AgentWorkRow:
    """写入或覆盖对话快照。"""
    key = work_id.strip()
    title = str(detail.get("title") or "").strip() or key
    payload = dict(detail)
    payload["work_id"] = key
    now = time.time()
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    with _connection() as conn:
        existing = conn.execute(
            "SELECT created_at FROM agent_works WHERE work_id = ?",
            (key,),
        ).fetchone()
        created_at = float(existing["created_at"]) if existing else now
        conn.execute(
            """
            INSERT INTO agent_works (work_id, title, detail_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(work_id) DO UPDATE SET
                title = excluded.title,
                detail_json = excluded.detail_json,
                updated_at = excluded.updated_at
            """,
            (key, title, blob, created_at, now),
        )

    logger.debug("agent work saved work_id=%s title=%s", key, title[:40])
    return AgentWorkRow(
        work_id=key,
        title=title,
        detail=payload,
        created_at=created_at,
        updated_at=now,
    )
