"""副驾 pipe RPC handlers。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from dingda_sidecar.runtime.handlers.copilot import (
    handle_copilot_run_abort,
    handle_copilot_run_start,
)


class TestCopilotPipeHandlers(unittest.TestCase):
    @patch("dingda_sidecar.runtime.handlers.copilot.run_copilot_run")
    @patch("dingda_sidecar.runtime.handlers.copilot.register_run")
    def test_run_start_returns_ids(self, _register, _run) -> None:
        result = handle_copilot_run_start(
            {
                "threadId": "t1",
                "runId": "r1",
                "messages": [{"role": "user", "content": "hi"}],
                "default_api_key": "sk",
                "default_model": "m",
            },
            trace_id="trace",
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["run_id"], "r1")
        self.assertEqual(result["thread_id"], "t1")

    @patch("dingda_sidecar.runtime.handlers.copilot.get_run")
    def test_run_abort_cancels_active(self, get_run) -> None:
        import threading

        run = type("Run", (), {"cancelled": threading.Event()})()
        get_run.return_value = run
        result = handle_copilot_run_abort({"run_id": "r1"}, trace_id="trace")
        self.assertTrue(result["ok"])
        self.assertTrue(run.cancelled.is_set())


if __name__ == "__main__":
    unittest.main()
