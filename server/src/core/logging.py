"""统一 ANSI 控制台日志（与 Rust `[shell]` 风格一致）。

业务代码只用::

    from src.core.logging import info

    info("启动应用")
    info("启动应用", {"port": 8787})
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, TextIO

_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})
_CONTEXT_KEY = "_ctx"

_PREFIX = "\x1b[1;32m[server]\x1b[0m"
_RESET = "\x1b[0m"
_LEVEL_COLORS = {
    "DEBUG": "\x1b[36m",
    "INFO": "\x1b[32m",
    "WARNING": "\x1b[33m",
    "ERROR": "\x1b[31m",
    "CRITICAL": "\x1b[1;31m",
}
_BEIJING_TZ = timezone(timedelta(hours=8))
_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def _ensure_utf8(stream: TextIO) -> TextIO:
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    return stream


def _format_context(record: logging.LogRecord) -> str:
    context = record.__dict__.get(_CONTEXT_KEY)
    if not context:
        return ""
    return " ".join(f"{key}={value!r}" for key, value in context.items())


class _BusinessLogFilter(logging.Filter):
    """输出 dingda 业务日志（含 dingda.channel.* 子 logger）。"""

    def filter(self, record: logging.LogRecord) -> bool:
        name = record.name
        return name == "dingda" or name.startswith("dingda.")


class ServerFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        color = _LEVEL_COLORS.get(record.levelname, "")
        level = f"{color}{record.levelname:<8}{_RESET}"
        timestamp = datetime.fromtimestamp(record.created, _BEIJING_TZ).strftime(
            _TIME_FORMAT
        )
        message = f"{record.getMessage()}{_format_context(record)}"
        return f"{_PREFIX} {timestamp} {level} {record.name}  {message}"


def configure_logging(*, level: str = "INFO") -> None:
    normalized = level.upper()
    if normalized not in _LOG_LEVELS:
        normalized = "INFO"

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(ServerFormatter())
    handler.addFilter(_BusinessLogFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(normalized)

    logging.getLogger("dingda").propagate = True
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "watchfiles"):
        logging.getLogger(name).setLevel(logging.WARNING)

    _ensure_utf8(sys.stderr)


def uvicorn_log_config(level: str = "INFO") -> dict[str, Any]:
    """仅供 ``uvicorn.run(log_config=...)``：不让 uvicorn 自己装 handler。"""
    normalized = level.upper()
    if normalized not in _LOG_LEVELS:
        normalized = "INFO"

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "loggers": {
            "uvicorn": {"handlers": [], "level": "WARNING", "propagate": True},
            "uvicorn.error": {"handlers": [], "level": "WARNING", "propagate": True},
            "uvicorn.access": {"handlers": [], "level": "WARNING", "propagate": True},
        },
    }


def _log(level: int, message: str, context: dict[str, Any] | None = None) -> None:
    extra = {_CONTEXT_KEY: context} if context else {}
    logging.getLogger("dingda").log(level, message, extra=extra)


def debug(message: str, context: dict[str, Any] | None = None) -> None:
    _log(logging.DEBUG, message, context)


def info(message: str, context: dict[str, Any] | None = None) -> None:
    _log(logging.INFO, message, context)


def warning(message: str, context: dict[str, Any] | None = None) -> None:
    _log(logging.WARNING, message, context)


def error(message: str, context: dict[str, Any] | None = None) -> None:
    _log(logging.ERROR, message, context)
