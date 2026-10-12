"""core.logging 文件落盘验证：纯文本、轮转参数、默认不落盘。"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from core.logging import bind_trace, configure_logging, info, reset_trace


def _reset() -> None:
    """关掉全部 handler（含落盘文件句柄）后还原为仅 stderr，避免跨测试泄漏。"""
    for handler in list(logging.getLogger().handlers):
        handler.close()
    configure_logging(level="INFO")


def test_log_file_receives_plain_lines(tmp_path) -> None:
    log_file = tmp_path / "logs" / "server.log"

    configure_logging(level="INFO", log_file=log_file)
    try:
        info("启动应用", {"port": 8787})

        text = log_file.read_text(encoding="utf-8")
        assert "启动应用" in text
        assert "port=8787" in text
        assert text.startswith("[server] ")
        assert "\x1b" not in text  # 文件内无 ANSI 色码
    finally:
        _reset()


def test_log_file_defaults_to_console_only() -> None:
    configure_logging(level="INFO")

    handlers = logging.getLogger().handlers
    assert len(handlers) == 1
    assert isinstance(handlers[0], logging.StreamHandler)
    assert not isinstance(handlers[0], RotatingFileHandler)


def test_file_handler_rotation_params(tmp_path) -> None:
    log_file = tmp_path / "server.log"

    configure_logging(level="INFO", log_file=log_file)
    try:
        file_handler = next(
            h for h in logging.getLogger().handlers if isinstance(h, RotatingFileHandler)
        )
        assert file_handler.maxBytes == 5 * 1024 * 1024
        assert file_handler.backupCount == 5
    finally:
        _reset()


def test_trace_id_appended_then_reset(tmp_path) -> None:
    """bind_trace 后行尾带 trace=<id>；reset 后不串号（SSE runId 同源）。"""
    log_file = tmp_path / "server.log"

    configure_logging(level="INFO", log_file=log_file)
    try:
        token = bind_trace("run-abc123")
        info("工具调用", {"tool": "search"})
        reset_trace(token)
        info("已还原")

        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        assert "工具调用" in lines[0]
        assert "trace=run-abc123" in lines[0]
        assert "trace=" not in lines[1]
    finally:
        _reset()
