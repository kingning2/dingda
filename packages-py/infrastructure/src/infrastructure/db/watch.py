"""商品监控 SQLite 读写（``watch_targets`` + ``watch_points``）。

职责：
    维护被监控商品的目标行与其价格历史点；只做 SQL 与聚合，
    不做轮询、不做价格文本解析、不做结论推导。

设计说明：
    - ``watch_targets`` 是被监控商品的最新快照（首价/现价/最低价/最高价/售出态），
      列表接口直接读这一张表，不必扫点表
    - ``watch_points`` 是只增不改的时间序列；价格历史与降价事件都由它推导
    - 抓取失败不落点（避免把风控噪音写进价格序列），只记在目标行的
      ``fail_count`` / ``last_error``；但「商品不存在」要落点，因为下架/售出
      本身就是要观察的信号，由调用方以 ``sold_state='gone'`` 传入
    - 调用方：``domains.watch``

使用示例：
    row = upsert_target(platform="xianyu", item_id="123", poll_interval_seconds=21600)
    save_poll_snapshot(target_id=row.target_id, sold_state="on_sale", price=88.0, ...)
"""

from __future__ import annotations

import logging
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from infrastructure.db.schema import WATCH_POINTS_TABLE_SQL, WATCH_TARGETS_TABLE_SQL
from infrastructure.db.session import db_path

logger = logging.getLogger("dingda.db.watch")

DEFAULT_POLL_INTERVAL_SECONDS = 6 * 3600

# 本层只把 state 当落库值筛选，不解释语义；词表真相源在 contracts.watch.WatchState
# （本包零依赖，不能 import）。改这里的值等于改数据，必须配迁移。
TARGET_ACTIVE = "active"

# 售出态本层只负责存取，不解释取值；默认值对应 contracts.watch.SoldState.UNKNOWN。
_SOLD_STATE_UNKNOWN = "unknown"

_TARGET_COLUMNS = (
    "target_id, platform, item_id, title, url, image_url, account_id, state, sold_state, "
    "first_price, last_price, min_price, max_price, last_want_count, last_status_text, "
    "poll_interval_seconds, next_poll_at, last_poll_at, last_error, fail_count, "
    "created_at, updated_at"
)


@dataclass(frozen=True, slots=True)
class WatchTargetRow:
    """一条被监控商品的最新快照。"""

    target_id: str
    platform: str
    item_id: str
    title: str
    url: str
    image_url: str | None
    account_id: str | None
    state: str
    sold_state: str
    first_price: float | None
    last_price: float | None
    min_price: float | None
    max_price: float | None
    last_want_count: str | None
    last_status_text: str | None
    poll_interval_seconds: int
    next_poll_at: float
    last_poll_at: float | None
    last_error: str | None
    fail_count: int
    created_at: float
    updated_at: float


@dataclass(frozen=True, slots=True)
class WatchPointRow:
    """价格历史上的一个观测点。"""

    point_id: int
    target_id: str
    price: float | None
    price_text: str | None
    want_count: str | None
    browse_count: str | None
    status_text: str | None
    sold_state: str
    observed_at: float


def ensure_schema() -> None:
    """确保 watch_targets / watch_points 两张表存在。"""
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(WATCH_TARGETS_TABLE_SQL)
        conn.executescript(WATCH_POINTS_TABLE_SQL)


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


def _row_to_target(row: sqlite3.Row) -> WatchTargetRow:
    return WatchTargetRow(
        target_id=str(row["target_id"]),
        platform=str(row["platform"]),
        item_id=str(row["item_id"]),
        title=str(row["title"]),
        url=str(row["url"]),
        image_url=str(row["image_url"]) if row["image_url"] else None,
        account_id=str(row["account_id"]) if row["account_id"] else None,
        state=str(row["state"]),
        sold_state=str(row["sold_state"]),
        first_price=_optional_float(row["first_price"]),
        last_price=_optional_float(row["last_price"]),
        min_price=_optional_float(row["min_price"]),
        max_price=_optional_float(row["max_price"]),
        last_want_count=str(row["last_want_count"]) if row["last_want_count"] else None,
        last_status_text=str(row["last_status_text"]) if row["last_status_text"] else None,
        poll_interval_seconds=int(row["poll_interval_seconds"]),
        next_poll_at=float(row["next_poll_at"]),
        last_poll_at=_optional_float(row["last_poll_at"]),
        last_error=str(row["last_error"]) if row["last_error"] else None,
        fail_count=int(row["fail_count"]),
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
    )


def _row_to_point(row: sqlite3.Row) -> WatchPointRow:
    return WatchPointRow(
        point_id=int(row["point_id"]),
        target_id=str(row["target_id"]),
        price=_optional_float(row["price"]),
        price_text=str(row["price_text"]) if row["price_text"] else None,
        want_count=str(row["want_count"]) if row["want_count"] else None,
        browse_count=str(row["browse_count"]) if row["browse_count"] else None,
        status_text=str(row["status_text"]) if row["status_text"] else None,
        sold_state=str(row["sold_state"]),
        observed_at=float(row["observed_at"]),
    )


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def upsert_target(
    *,
    platform: str,
    item_id: str,
    poll_interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS,
    title: str = "",
    url: str = "",
    image_url: str | None = None,
    account_id: str | None = None,
    first_price: float | None = None,
) -> WatchTargetRow:
    """把商品加入监控；已存在则复用原行，不重置价格历史与轮询进度。

    若原行处于 paused / archived，则顺手恢复为 active——重新加入的意图就是继续监控。
    """
    key = find_target_id(platform, item_id)
    if key:
        existing = get_target(key)
        if existing is not None:
            logger.info(
                "watch target already exists target_id=%s platform=%s item_id=%s state=%s",
                key,
                platform,
                item_id,
                existing.state,
            )
            if existing.state != TARGET_ACTIVE:
                resumed = set_target_state(key, TARGET_ACTIVE)
                return resumed if resumed is not None else existing
            return existing

    target_id = f"watch-{uuid.uuid4().hex[:12]}"
    now = time.time()
    interval = max(60, int(poll_interval_seconds))
    with _connection() as conn:
        conn.execute(
            """
            INSERT INTO watch_targets (
                target_id, platform, item_id, title, url, image_url, account_id,
                state, sold_state, first_price, last_price, min_price, max_price,
                poll_interval_seconds, next_poll_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                target_id,
                platform,
                item_id,
                title,
                url,
                image_url,
                account_id,
                TARGET_ACTIVE,
                _SOLD_STATE_UNKNOWN,
                first_price,
                first_price,
                first_price,
                first_price,
                interval,
                now,
                now,
                now,
            ),
        )
    logger.info(
        "watch target added target_id=%s platform=%s item_id=%s interval=%s",
        target_id,
        platform,
        item_id,
        interval,
    )
    created = get_target(target_id)
    if created is None:
        raise RuntimeError(f"监控目标写入失败：{target_id}")
    return created


def get_target(target_id: str) -> WatchTargetRow | None:
    """按 target_id 读监控目标。"""
    key = target_id.strip()
    if not key:
        return None
    with _connection() as conn:
        row = conn.execute(
            f"SELECT {_TARGET_COLUMNS} FROM watch_targets WHERE target_id = ?",
            (key,),
        ).fetchone()
    return _row_to_target(row) if row else None


def find_target_id(platform: str, item_id: str) -> str | None:
    """按 (platform, item_id) 找 target_id，用于加入监控时去重。"""
    with _connection() as conn:
        row = conn.execute(
            "SELECT target_id FROM watch_targets WHERE platform = ? AND item_id = ?",
            (platform.strip(), item_id.strip()),
        ).fetchone()
    return str(row["target_id"]) if row else None


def list_targets(
    *,
    state: str | None = None,
    limit: int = 200,
) -> list[WatchTargetRow]:
    """列出监控目标，按创建时间倒序；``state`` 为空则不限状态。"""
    cap = max(1, min(int(limit), 1000))
    with _connection() as conn:
        if state:
            rows = conn.execute(
                f"SELECT {_TARGET_COLUMNS} FROM watch_targets "
                "WHERE state = ? ORDER BY created_at DESC LIMIT ?",
                (state, cap),
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {_TARGET_COLUMNS} FROM watch_targets "
                "ORDER BY created_at DESC LIMIT ?",
                (cap,),
            ).fetchall()
    return [_row_to_target(row) for row in rows]


def list_due_targets(*, now: float | None = None, limit: int = 50) -> list[WatchTargetRow]:
    """取已到轮询时间的活跃目标，最该跑的排前面。"""
    moment = time.time() if now is None else float(now)
    cap = max(1, int(limit))
    with _connection() as conn:
        rows = conn.execute(
            f"SELECT {_TARGET_COLUMNS} FROM watch_targets "
            "WHERE state = ? AND next_poll_at <= ? "
            "ORDER BY next_poll_at ASC LIMIT ?",
            (TARGET_ACTIVE, moment, cap),
        ).fetchall()
    return [_row_to_target(row) for row in rows]


def count_active() -> int:
    """活跃监控目标数量，供调度器决定错开步长。"""
    with _connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM watch_targets WHERE state = ?",
            (TARGET_ACTIVE,),
        ).fetchone()
    return int(row["n"]) if row else 0


def set_target_state(target_id: str, state: str) -> WatchTargetRow | None:
    """切换监控状态（active / paused / archived）。"""
    now = time.time()
    with _connection() as conn:
        conn.execute(
            "UPDATE watch_targets SET state = ?, updated_at = ? WHERE target_id = ?",
            (state, now, target_id),
        )
    logger.info("watch target state=%s target_id=%s", state, target_id)
    return get_target(target_id)


def set_poll_interval(target_id: str, seconds: int) -> WatchTargetRow | None:
    """调整轮询间隔；下一次轮询时间同步前推，避免沿用旧节奏。"""
    interval = max(60, int(seconds))
    now = time.time()
    with _connection() as conn:
        conn.execute(
            """
            UPDATE watch_targets
            SET poll_interval_seconds = ?, next_poll_at = ?, updated_at = ?
            WHERE target_id = ?
            """,
            (interval, now + interval, now, target_id),
        )
    logger.info("watch target interval=%s target_id=%s", interval, target_id)
    return get_target(target_id)


def save_poll_snapshot(
    *,
    target_id: str,
    sold_state: str,
    price: float | None,
    next_poll_at: float,
    status_text: str | None = None,
    want_count: str | None = None,
    title: str | None = None,
    observed_at: float | None = None,
) -> WatchTargetRow | None:
    """轮询成功后写回最新快照，并推进首价/最低价/最高价聚合。

    ``title`` 只在目标还没有标题时回填——用户可能只拿 item_id 建监控，
    标题要等第一次抓到详情才补上。
    """
    moment = time.time() if observed_at is None else float(observed_at)
    current = get_target(target_id)
    if current is None:
        return None

    first = current.first_price if current.first_price is not None else price
    last = price if price is not None else current.last_price
    if price is None:
        low = current.min_price
        high = current.max_price
    else:
        low = price if current.min_price is None else min(current.min_price, price)
        high = price if current.max_price is None else max(current.max_price, price)
    resolved_title = current.title or (title or "")

    with _connection() as conn:
        conn.execute(
            """
            UPDATE watch_targets
            SET sold_state = ?, last_status_text = ?, last_want_count = ?, title = ?,
                first_price = ?, last_price = ?, min_price = ?, max_price = ?,
                last_poll_at = ?, next_poll_at = ?, fail_count = 0,
                last_error = NULL, updated_at = ?
            WHERE target_id = ?
            """,
            (
                sold_state,
                status_text,
                want_count,
                resolved_title,
                first,
                last,
                low,
                high,
                moment,
                next_poll_at,
                moment,
                target_id,
            ),
        )
    return get_target(target_id)


def record_poll_failure(
    *,
    target_id: str,
    error: str,
    next_poll_at: float,
    observed_at: float | None = None,
) -> WatchTargetRow | None:
    """轮询失败：累计失败次数、记错误、后推下一次；不动价格快照。"""
    moment = time.time() if observed_at is None else float(observed_at)
    with _connection() as conn:
        conn.execute(
            """
            UPDATE watch_targets
            SET fail_count = fail_count + 1, last_error = ?,
                last_poll_at = ?, next_poll_at = ?, updated_at = ?
            WHERE target_id = ?
            """,
            (error[:400], moment, next_poll_at, moment, target_id),
        )
    return get_target(target_id)


def set_next_poll_at(target_id: str, next_poll_at: float) -> None:
    """只改下一次轮询时间。

    调度器先按「成功」算好时间交给 ``poller``，失败时再用本函数覆盖成退避时间，
    这样不必让 poller 反过来知道退避策略，也不会把 fail_count 加两次。
    """
    with _connection() as conn:
        conn.execute(
            "UPDATE watch_targets SET next_poll_at = ?, updated_at = ? WHERE target_id = ?",
            (float(next_poll_at), time.time(), target_id),
        )


def add_point(
    *,
    target_id: str,
    sold_state: str,
    price: float | None = None,
    price_text: str | None = None,
    want_count: str | None = None,
    browse_count: str | None = None,
    status_text: str | None = None,
    observed_at: float | None = None,
) -> WatchPointRow:
    """追加一个价格历史点。"""
    moment = time.time() if observed_at is None else float(observed_at)
    with _connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO watch_points (
                target_id, price, price_text, want_count, browse_count,
                status_text, sold_state, observed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                target_id,
                price,
                price_text,
                want_count,
                browse_count,
                status_text,
                sold_state,
                moment,
            ),
        )
        point_id = int(cursor.lastrowid or 0)
    logger.debug(
        "watch point added target_id=%s point_id=%s price=%s state=%s",
        target_id,
        point_id,
        price,
        sold_state,
    )
    return WatchPointRow(
        point_id=point_id,
        target_id=target_id,
        price=price,
        price_text=price_text,
        want_count=want_count,
        browse_count=browse_count,
        status_text=status_text,
        sold_state=sold_state,
        observed_at=moment,
    )


def list_points(*, target_id: str, limit: int = 500) -> list[WatchPointRow]:
    """读某目标的价格历史点，按时间正序（便于画曲线与比相邻点）。"""
    cap = max(1, min(int(limit), 5000))
    with _connection() as conn:
        rows = conn.execute(
            """
            SELECT point_id, target_id, price, price_text, want_count, browse_count,
                   status_text, sold_state, observed_at
            FROM watch_points
            WHERE target_id = ?
            ORDER BY observed_at ASC, point_id ASC
            LIMIT ?
            """,
            (target_id, cap),
        ).fetchall()
    return [_row_to_point(row) for row in rows]


def delete_target(target_id: str) -> bool:
    """彻底删除监控目标及其全部价格历史点。"""
    with _connection() as conn:
        conn.execute("DELETE FROM watch_points WHERE target_id = ?", (target_id,))
        cursor = conn.execute("DELETE FROM watch_targets WHERE target_id = ?", (target_id,))
    removed = cursor.rowcount > 0
    logger.info("watch target deleted target_id=%s removed=%s", target_id, removed)
    return removed
