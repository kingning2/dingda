"""闲鱼写操作令牌桶。

职责：
    单账号命名空间限流（默认每分钟 1 次写），状态落在产品数据目录，
    供 publish / delete / send / upload 共用。

设计说明：
    - 对齐 goofish_cli core/limiter，不写 ~/.goofish-cli
    - 环境变量 DINGDA_WRITE_RPM 可调上限

使用示例：
    with acquire("item.write"):
        delete(cookie, item_id)
"""

from __future__ import annotations

import json
import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path

from core.errors import rate_limited_error

logger = logging.getLogger("dingda.channel.xianyu.limiter")

DEFAULT_WRITE_RPM = 1


def _rpm() -> int:
    try:
        return max(1, int(os.environ.get("DINGDA_WRITE_RPM", DEFAULT_WRITE_RPM)))
    except ValueError:
        return DEFAULT_WRITE_RPM


def _state_path() -> Path:
    from infrastructure.db.session import data_dir

    return data_dir() / "xianyu" / "limiter.json"


def _load() -> dict[str, list[float]]:
    path = _state_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save(state: dict[str, list[float]]) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state), encoding="utf-8")


def check(bucket: str) -> None:
    """消耗一个令牌；超限抛 channel.rate_limited。"""
    now = time.time()
    window = 60.0
    rpm = _rpm()
    state = _load()
    hits = [t for t in state.get(bucket, []) if now - t < window]
    if len(hits) >= rpm:
        wait = window - (now - hits[0])
        raise rate_limited_error(
            f"限流：bucket={bucket} 每 {window:.0f}s 上限 {rpm}，再等 {wait:.1f}s"
        )
    hits.append(now)
    state[bucket] = hits
    _save(state)
    logger.debug("limiter acquire bucket=%s hits=%s", bucket, len(hits))


@contextmanager
def acquire(bucket: str):
    """写操作入口：先 check 再执行。"""
    check(bucket)
    yield
