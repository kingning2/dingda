"""Contract-compatible JSON Lines logging for the Python sidecar."""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import traceback
from collections.abc import Iterator, Mapping
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any, TextIO

_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_ENVIRONMENTS = {"development", "production"}
_CONTEXT_FIELDS = ("trace_id", "task_id", "feature", "tenant_id")
_TOP_LEVEL_FIELDS = {*_CONTEXT_FIELDS, "event"}
# 消息长度上限：需容纳二维码 base64（data URL 约 40-55KB）。
_MESSAGE_LIMIT = 200_000
_PREVIEW_LIMIT = 1000
_STACK_LIMIT = 8000
_REDACTED = "[REDACTED]"

_context: ContextVar[dict[str, str] | None] = ContextVar("dingda_log_context", default=None)

_EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])")
_PHONE_RE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_SECRET_RE = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|token|secret|password)\b"
    r"(\s*[:=]\s*)([^\s,;]+)"
)
_WINDOWS_PATH_RE = re.compile(r"(?i)(?:[A-Z]:\\)(?:[^\s\"']+\\)+([^\\\s\"']+)")
_POSIX_PATH_RE = re.compile(r"(?<![\w.])/(?:[^\s\"']+/)+([^/\s\"']+)")
_SENSITIVE_KEYS = re.compile(r"(?i)(api[_-]?key|token|secret|password|authorization)")

_RESERVED_RECORD_FIELDS = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


def sanitize_text(value: str) -> str:
    """Redact common credentials and customer identifiers from text."""
    sanitized = _BEARER_RE.sub(f"Bearer {_REDACTED}", value)
    sanitized = _SECRET_RE.sub(
        lambda match: f"{match.group(1)}{match.group(2)}{_REDACTED}", sanitized
    )
    sanitized = _EMAIL_RE.sub(_REDACTED, sanitized)
    return _PHONE_RE.sub(_REDACTED, sanitized)


def payload_preview(
    value: str,
    *,
    environment: str | None = None,
    limit: int = _PREVIEW_LIMIT,
) -> dict[str, object]:
    """Return a safe development preview without exposing production payload text."""
    active_environment = _get_environment(environment)
    result: dict[str, object] = {
        "length": len(value),
        "truncated": len(value) > limit,
    }
    if active_environment == "development":
        result["preview"] = sanitize_text(value[:limit])
    return result


@contextmanager
def bind_log_context(
    *,
    trace_id: str | None = None,
    task_id: str | None = None,
    feature: str | None = None,
    tenant_id: str | None = None,
) -> Iterator[None]:
    """Bind correlation fields for logs emitted inside this sync or async context."""
    additions = {
        key: value
        for key, value in {
            "trace_id": trace_id,
            "task_id": task_id,
            "feature": feature,
            "tenant_id": tenant_id,
        }.items()
        if value is not None
    }
    token = _context.set({**(_context.get() or {}), **additions})
    try:
        yield
    finally:
        _context.reset(token)


class JsonLineFormatter(logging.Formatter):
    """Format a LogRecord as one runtime/log/entry/v1 JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        try:
            return json.dumps(
                self._build_entry(record),
                ensure_ascii=False,
                separators=(",", ":"),
                default=_json_default,
            )
        except Exception as error:  # noqa: BLE001 - logging must never crash the sidecar
            fallback = {
                "schema_version": "1",
                "timestamp": _timestamp(record.created),
                "level": "ERROR",
                "source": "python",
                "logger": "dingda.logging",
                "message": "log serialization failed",
                "attributes": {
                    "original_logger": sanitize_text(record.name),
                    "error_type": type(error).__name__,
                },
            }
            return json.dumps(fallback, ensure_ascii=False, separators=(",", ":"))

    def _build_entry(self, record: logging.LogRecord) -> dict[str, object]:
        raw_message = record.getMessage()
        # 二维码 data URL 是图片内容，跳过敏感信息清洗，避免手机号/密钥正则误伤 base64。
        if raw_message.startswith("data:image/"):
            message = _truncate(raw_message, _MESSAGE_LIMIT)
        else:
            message = _truncate(sanitize_text(raw_message), _MESSAGE_LIMIT)
        entry: dict[str, object] = {
            "schema_version": "1",
            "timestamp": _timestamp(record.created),
            "level": _normalize_record_level(record.levelname),
            "source": "python",
            "logger": sanitize_text(record.name),
            "message": message,
        }

        context = _context.get() or {}
        for field in _TOP_LEVEL_FIELDS:
            value = getattr(record, field, None)
            if value is None:
                value = context.get(field)
            if value is not None:
                entry[field] = _truncate(sanitize_text(str(value)), _PREVIEW_LIMIT)

        attributes = {
            key: _sanitize_value(value, key=key)
            for key, value in record.__dict__.items()
            if key not in _RESERVED_RECORD_FIELDS and key not in _TOP_LEVEL_FIELDS
        }
        if attributes:
            entry["attributes"] = attributes

        if record.exc_info is not None:
            exception_type = record.exc_info[0]
            exception_value = record.exc_info[1]
            raw_stack = "".join(traceback.format_exception(*record.exc_info))
            entry["exception"] = {
                "type": exception_type.__name__ if exception_type else "Exception",
                "message": _truncate(sanitize_text(str(exception_value)), _PREVIEW_LIMIT),
                "stack": _sanitize_stack(raw_stack),
            }

        return entry


def _ensure_utf8(stream: TextIO) -> TextIO:
    """强制 UTF-8 输出。

    Windows 控制台/管道默认 GBK：JSON 日志会乱码，且含非 GBK 字符时
    `stream.write` 抛 `UnicodeEncodeError`，被 Rust 侧转成 stderr 刷屏。
    Rust 端按 UTF-8 读取日志，因此这里必须统一。
    """
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is not None:
        with suppress(Exception):
            reconfigure(encoding="utf-8", errors="replace")
    return stream


def configure_logging(*, stream: TextIO | None = None) -> None:
    """Configure the root logger to emit v1 JSON Lines to stdout."""
    if stream is None:
        stream = _ensure_utf8(sys.stdout)
        _ensure_utf8(sys.stderr)
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JsonLineFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(_get_log_level())

    configured_level = os.getenv("DINGDA_LOG_LEVEL", "INFO").upper()
    if configured_level not in _LOG_LEVELS:
        logging.getLogger("dingda.logging").warning(
            "invalid log level; falling back to INFO",
            extra={"event": "logging.invalid_level"},
        )


def _get_log_level() -> str:
    candidate = os.getenv("DINGDA_LOG_LEVEL", "INFO").upper()
    return candidate if candidate in _LOG_LEVELS else "INFO"


def _get_environment(value: str | None = None) -> str:
    candidate = (value or os.getenv("DINGDA_ENV", "production")).lower()
    return candidate if candidate in _ENVIRONMENTS else "production"


def _normalize_record_level(value: str) -> str:
    normalized = value.upper()
    if normalized == "WARN":
        return "WARNING"
    return normalized if normalized in _LOG_LEVELS else "INFO"


def _sanitize_value(value: Any, *, key: str = "") -> object:
    if _SENSITIVE_KEYS.search(key):
        return _REDACTED
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        return _truncate(sanitize_text(value), _PREVIEW_LIMIT)
    if isinstance(value, Mapping):
        return {
            str(item_key): _sanitize_value(item, key=str(item_key))
            for item_key, item in value.items()
        }
    if isinstance(value, list | tuple | set | frozenset):
        return [_sanitize_value(item) for item in value]
    return _truncate(sanitize_text(repr(value)), _PREVIEW_LIMIT)


def _sanitize_stack(value: str) -> str:
    sanitized = sanitize_text(value)
    sanitized = _WINDOWS_PATH_RE.sub(r"<path>\\\1", sanitized)
    sanitized = _POSIX_PATH_RE.sub(r"<path>/\1", sanitized)
    return _truncate(sanitized, _STACK_LIMIT)


def _truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[:limit]


def _timestamp(created: float) -> str:
    return (
        datetime.fromtimestamp(created, tz=UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _json_default(value: object) -> str:
    return _truncate(sanitize_text(repr(value)), _PREVIEW_LIMIT)
