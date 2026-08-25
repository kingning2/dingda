"""JSON Lines 日志格式与配置单元测试。

断言必填字段、脱敏与 ``configure_logging`` 在环境变量下的行为。"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PYTHON_ROOT = Path(__file__).resolve().parents[1]
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))

from crawlers.core.logging import (  # noqa: E402
    JsonLineFormatter,
    bind_log_context,
    configure_logging,
    payload_preview,
)

_REQUIRED_FIELDS = {"schema_version", "timestamp", "level", "source", "logger", "message"}
_ALLOWED_FIELDS = _REQUIRED_FIELDS | {
    "event",
    "feature",
    "trace_id",
    "task_id",
    "tenant_id",
    "attributes",
    "exception",
}


class JsonLineFormatterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.formatter = JsonLineFormatter()

    def format_record(self, message: str, **extra: object) -> dict[str, object]:
        record = logging.LogRecord("dingda.test", logging.INFO, __file__, 1, message, (), None)
        for key, value in extra.items():
            setattr(record, key, value)
        rendered = self.formatter.format(record)
        self.assertNotIn("\n", rendered)
        return json.loads(rendered)

    def test_contract_shape_and_unicode_are_preserved(self) -> None:
        entry = self.format_record("你好\nDingDa", event="test.started")

        self.assertTrue(entry.keys() >= _REQUIRED_FIELDS)
        self.assertTrue(entry.keys() <= _ALLOWED_FIELDS)
        self.assertEqual(entry["schema_version"], "1")
        self.assertEqual(entry["source"], "python")
        self.assertEqual(entry["message"], "你好\nDingDa")

    def test_context_is_bound_and_restored(self) -> None:
        with bind_log_context(trace_id="trace-1", task_id="task-1", feature="agent"):
            entry = self.format_record("inside")
        outside = self.format_record("outside")

        self.assertEqual(entry["trace_id"], "trace-1")
        self.assertEqual(entry["task_id"], "task-1")
        self.assertEqual(entry["feature"], "agent")
        self.assertNotIn("trace_id", outside)

    def test_async_contexts_do_not_leak(self) -> None:
        async def emit(trace_id: str) -> str:
            with bind_log_context(trace_id=trace_id):
                await asyncio.sleep(0)
                return str(self.format_record("async")["trace_id"])

        async def gather() -> list[str]:
            return list(await asyncio.gather(emit("trace-a"), emit("trace-b")))

        self.assertEqual(asyncio.run(gather()), ["trace-a", "trace-b"])

    def test_attributes_are_sanitized_and_unserializable_values_degrade(self) -> None:
        sensitive_field = "api_key"
        sensitive_value = "sample-credential"
        entry = self.format_record(
            "attributes",
            **{
                sensitive_field: sensitive_value,
                "custom": object(),
                "email": "person@example.com",
            },
        )
        attributes = entry["attributes"]

        self.assertIsInstance(attributes, dict)
        self.assertEqual(attributes["api_key"], "[REDACTED]")
        self.assertEqual(attributes["email"], "[REDACTED]")
        self.assertIsInstance(attributes["custom"], str)

    def test_exception_contains_sanitized_limited_stack(self) -> None:
        try:
            raise RuntimeError("token=sample-credential person@example.com")
        except RuntimeError:
            record = logging.LogRecord(
                "dingda.test",
                logging.ERROR,
                r"C:\Users\Developer\project\module.py",
                1,
                "failed",
                (),
                sys.exc_info(),
            )

        entry = json.loads(self.formatter.format(record))
        exception = entry["exception"]

        self.assertEqual(exception["type"], "RuntimeError")
        self.assertNotIn("sample-credential", exception["stack"])
        self.assertNotIn("person@example.com", exception["stack"])
        self.assertLessEqual(len(exception["stack"]), 8000)


class LoggingConfigurationTests(unittest.TestCase):
    def tearDown(self) -> None:
        logging.getLogger().handlers.clear()

    def test_invalid_log_level_falls_back_to_info(self) -> None:
        stream = io.StringIO()
        with patch.dict(os.environ, {"DINGDA_LOG_LEVEL": "verbose"}):
            configure_logging(stream=stream)

        self.assertEqual(logging.getLogger().level, logging.INFO)
        warning = json.loads(stream.getvalue().splitlines()[0])
        self.assertEqual(warning["event"], "logging.invalid_level")

    def test_sidecar_log_env_writes_to_shared_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "logs", "sidecar.log")
            with patch.dict(os.environ, {"DINGDA_SIDECAR_LOG": log_path}):
                configure_logging()
                logging.getLogger("dingda.test").info("共享日志测试")
                for handler in list(logging.getLogger().handlers):
                    handler.close()

            with open(log_path, encoding="utf-8") as fh:
                entry = json.loads(fh.readline())
        self.assertEqual(entry["message"], "共享日志测试")
        self.assertEqual(entry["source"], "python")

    def test_development_preview_is_truncated_and_sanitized(self) -> None:
        text = "person@example.com token=sample-credential " + ("x" * 1200)
        preview = payload_preview(text, environment="development")

        self.assertEqual(preview["length"], len(text))
        self.assertTrue(preview["truncated"])
        self.assertNotIn("person@example.com", preview["preview"])
        self.assertNotIn("sample-credential", preview["preview"])
        self.assertLessEqual(len(preview["preview"]), 1000)

    def test_production_preview_does_not_contain_payload(self) -> None:
        preview = payload_preview("customer private message", environment="production")

        self.assertNotIn("preview", preview)
        self.assertEqual(preview["length"], 24)


if __name__ == "__main__":
    unittest.main()
