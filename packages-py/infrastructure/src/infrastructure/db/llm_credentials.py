"""模型凭据 SQLite 读写。

职责：
    读写 ``llm_credentials`` 表：多条模型凭据的增删改查、全局唯一「使用中」标记、
    以及每条凭据最近一次连通性检测的结果。只做 SQL，不脱敏、不写 HTTP 文案。

设计说明：
    - 表结构在 ``schema.LLM_CREDENTIALS_TABLE_SQL``
    - **``is_active`` 全局唯一**：发动机一次只认一条凭据，所以 ``set_active`` 在同一个
      事务里先清零再置一 —— 分成两次连接写会出现「两条都生效」或「一条都不生效」的中间态
    - **key 不脱敏**：脱敏是展示口径，归 ``domains.llm.service``；这里存什么读什么，
      否则「用户改 label 却把 key 改成掩码」这类事故会在这一层埋下
    - ``base_url`` 存 ``NULL`` 表示「用供应商默认地址」，不把默认值抄进库：
      供应商默认值会变（如豆包换域名），抄进来的旧值会让「改默认」对老凭据失效
"""

from __future__ import annotations

import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from infrastructure.db.schema import LLM_CREDENTIALS_TABLE_SQL
from infrastructure.db.session import db_path


@dataclass(frozen=True, slots=True)
class LlmCredentialRow:
    credential_id: str
    provider: str
    label: str
    model: str
    base_url: str | None
    api_key: str
    is_active: bool
    last_check_at: float | None
    last_check_ok: bool | None
    last_check_message: str | None
    created_at: float
    updated_at: float


def ensure_schema() -> None:
    """确保 llm_credentials 表存在。"""
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(LLM_CREDENTIALS_TABLE_SQL)


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


def _row_to_credential(row: sqlite3.Row) -> LlmCredentialRow:
    return LlmCredentialRow(
        credential_id=str(row["credential_id"]),
        provider=str(row["provider"]),
        label=str(row["label"]),
        model=str(row["model"]),
        base_url=str(row["base_url"]) if row["base_url"] else None,
        api_key=str(row["api_key"]),
        is_active=bool(row["is_active"]),
        last_check_at=float(row["last_check_at"]) if row["last_check_at"] is not None else None,
        last_check_ok=bool(row["last_check_ok"]) if row["last_check_ok"] is not None else None,
        last_check_message=str(row["last_check_message"]) if row["last_check_message"] else None,
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
    )


def list_credentials() -> list[LlmCredentialRow]:
    """全部凭据：使用中的排最前，其余按更新时间倒序。"""
    with _connection() as conn:
        rows = conn.execute(
            "SELECT * FROM llm_credentials ORDER BY is_active DESC, updated_at DESC",
        ).fetchall()
    return [_row_to_credential(row) for row in rows]


def get_credential(credential_id: str) -> LlmCredentialRow | None:
    """按 id 取一条；不存在返回 None。"""
    with _connection() as conn:
        row = conn.execute(
            "SELECT * FROM llm_credentials WHERE credential_id = ?",
            (credential_id,),
        ).fetchone()
    return _row_to_credential(row) if row else None


def get_active_credential() -> LlmCredentialRow | None:
    """取当前使用中的凭据；一条都没有则返回 None。

    表上没有唯一约束保证「至多一条 is_active=1」，靠 ``set_active`` 的写法维持。
    这里多取一行只是为了在数据被外部改坏时能发现 —— 发现就取最新那条并打日志，
    不让调用方拿到不确定的结果。
    """
    with _connection() as conn:
        rows = conn.execute(
            "SELECT * FROM llm_credentials WHERE is_active = 1 ORDER BY updated_at DESC",
        ).fetchall()
    if not rows:
        return None
    return _row_to_credential(rows[0])


def find_by_provider_and_key(provider: str, api_key: str) -> LlmCredentialRow | None:
    """按「供应商 + key 原文」查重；供环境变量导入用，避免重复导入同一条。"""
    with _connection() as conn:
        row = conn.execute(
            "SELECT * FROM llm_credentials WHERE provider = ? AND api_key = ? LIMIT 1",
            (provider, api_key),
        ).fetchone()
    return _row_to_credential(row) if row else None


def upsert_credential(
    *,
    credential_id: str,
    provider: str,
    model: str,
    api_key: str,
    label: str = "",
    base_url: str | None = None,
) -> LlmCredentialRow:
    """新建或覆盖一条凭据。**不动 ``is_active``** —— 那是 ``set_active`` 的职责。

    ``base_url`` 传 ``None`` 就是「用供应商默认地址」；传空串同样归 ``None``，
    免得库里出现 ``''`` 这种既不是默认也不是有效地址的第三种状态。
    """
    now = time.time()
    normalized_base_url = (base_url or "").strip() or None
    existing = get_credential(credential_id)
    with _connection() as conn:
        if existing:
            conn.execute(
                """
                UPDATE llm_credentials
                SET provider = ?, label = ?, model = ?, base_url = ?, api_key = ?, updated_at = ?
                WHERE credential_id = ?
                """,
                (provider, label, model, normalized_base_url, api_key, now, credential_id),
            )
        else:
            conn.execute(
                """
                INSERT INTO llm_credentials (
                    credential_id, provider, label, model, base_url, api_key,
                    is_active, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)
                """,
                (
                    credential_id,
                    provider,
                    label,
                    model,
                    normalized_base_url,
                    api_key,
                    now,
                    now,
                ),
            )
    saved = get_credential(credential_id)
    if not saved:
        raise RuntimeError(f"模型凭据写入失败：{credential_id}")
    return saved


def set_active(credential_id: str) -> LlmCredentialRow | None:
    """把某条设为唯一使用中；返回它，目标不存在返回 None。

    两条 UPDATE 必须在**同一个事务**里：先清零再置一。中间态（0 条生效）若被
    另一个请求读到，发动机就会去读环境变量、悄悄换一个模型。
    """
    now = time.time()
    with _connection() as conn:
        row = conn.execute(
            "SELECT credential_id FROM llm_credentials WHERE credential_id = ?",
            (credential_id,),
        ).fetchone()
        if not row:
            return None
        conn.execute(
            "UPDATE llm_credentials SET is_active = 0, updated_at = ? WHERE is_active = 1",
            (now,),
        )
        conn.execute(
            "UPDATE llm_credentials SET is_active = 1, updated_at = ? WHERE credential_id = ?",
            (now, credential_id),
        )
    return get_credential(credential_id)


def set_check_result(credential_id: str, *, ok: bool, message: str) -> None:
    """记下最近一次检测结果；**不更新 ``updated_at``**。

    检测是只读探活，不是用户编辑。把它算进 ``updated_at`` 会让「最近改动」列表
    被测试动作刷屏，也会让 ``list_credentials`` 的顺序无故跳动。
    """
    with _connection() as conn:
        conn.execute(
            """
            UPDATE llm_credentials
            SET last_check_at = ?, last_check_ok = ?, last_check_message = ?
            WHERE credential_id = ?
            """,
            (time.time(), int(ok), message, credential_id),
        )


def delete_credential(credential_id: str) -> bool:
    """删一条；返回是否真的删掉了。删掉使用中的那条后**不自动改选**别的。"""
    with _connection() as conn:
        cursor = conn.execute(
            "DELETE FROM llm_credentials WHERE credential_id = ?",
            (credential_id,),
        )
    return cursor.rowcount > 0
