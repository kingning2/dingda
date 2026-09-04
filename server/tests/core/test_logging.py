"""日志过滤器测试。"""

from __future__ import annotations

import logging

from src.core.logging import _BusinessLogFilter, configure_logging


def test_business_log_filter_allows_channel_loggers() -> None:
    filt = _BusinessLogFilter()
    assert filt.filter(logging.LogRecord("dingda", 0, "", 0, "", (), None)) is True
    assert filt.filter(logging.LogRecord("dingda.channel.xianyu", 0, "", 0, "", (), None)) is True
    assert filt.filter(logging.LogRecord("uvicorn", 0, "", 0, "", (), None)) is False


def test_configure_logging_emits_channel_logs(capsys) -> None:
    configure_logging(level="INFO")
    logging.getLogger("dingda.channel.test").info("probe ok")
    err = capsys.readouterr().err
    assert "dingda.channel.test" in err
    assert "probe ok" in err
