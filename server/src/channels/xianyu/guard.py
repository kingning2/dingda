"""闲鱼写操作风控熔断。

职责：
    命中 channel.risk 后写入冷却时间戳，冷却期内拒绝后续写；
    可用 reset 手动解除（对齐 goofish auth reset_guard）。

设计说明：
    - 状态落在产品数据目录，不写 ~/.goofish-cli
    - 环境变量 DINGDA_CIRCUIT_BREAK_MINUTES 控制冷却（默认 10 分钟）

使用示例：
    with hold():
        delete(cookie, item_id)
    reset()
"""

from __future__ import annotations

import json
import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path

from src.shared.errors import AppError, risk_control_error

logger = logging.getLogger("dingda.channel.xianyu.guard")

DEFAULT_BREAK_MINUTES = 10


def _break_seconds() -> int:
    try:
        minutes = int(os.environ.get("DINGDA_CIRCUIT_BREAK_MINUTES", DEFAULT_BREAK_MINUTES))
        return max(60, minutes * 60)
    except ValueError:
        return DEFAULT_BREAK_MINUTES * 60


def _state_path() -> Path:
    from src.infrastructure.db.session import data_dir

    return data_dir() / "xianyu" / "circuit.json"


def _load() -> float:
    path = _state_path()
    if not path.exists():
        return 0.0
    try:
        return float(json.loads(path.read_text(encoding="utf-8")).get("until", 0))
    except (json.JSONDecodeError, OSError, ValueError):
        return 0.0


def _save(until: float) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"until": until}), encoding="utf-8")


def check() -> None:
    """冷却期内直接拒绝。"""
    until = _load()
    if until and time.time() < until:
        remain = int(until - time.time())
        raise risk_control_error(f"风控熔断中，剩余 {remain}s")


def trip() -> None:
    """打开熔断。"""
    until = time.time() + _break_seconds()
    _save(until)
    logger.warning("guard trip until=%s", int(until))


def reset() -> None:
    """手动解除熔断。"""
    path = _state_path()
    if path.exists():
        path.unlink()
    logger.info("guard reset")


@contextmanager
def hold():
    """包住写操作：命中 channel.risk 自动熔断。"""
    check()
    try:
        yield
    except AppError as exc:
        if exc.code == "channel.risk":
            trip()
        raise
