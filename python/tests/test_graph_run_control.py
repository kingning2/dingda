"""Graph run control — pause / continue / restart / seek / cancel."""

from __future__ import annotations

import threading
import time
import unittest

from runtimes.langgraph.errors import ErrorKind, classify_exception
from runtimes.langgraph.handlers import (
    handle_agent_run_cancel,
    handle_agent_run_control,
    handle_agent_run_start,
    handle_agent_run_status,
)
from runtimes.langgraph.run_control import GraphRun, deep_copy_state, get_run_registry, new_run_id
from runtimes.langgraph.step_runner import PRICE_COMPARE_STEPS, build_initial_state, run_steps


class TestClassify(unittest.TestCase):
    def test_classify_billing_and_network(self) -> None:
        self.assertEqual(classify_exception(Exception("insufficient_quota")), ErrorKind.BILLING)
        self.assertEqual(classify_exception(Exception("connection timed out")), ErrorKind.NETWORK)
        self.assertEqual(classify_exception(Exception("429 rate limit")), ErrorKind.RATE_LIMIT)


class TestAgentRunHandlers(unittest.TestCase):
    def test_run_start_status_cancel(self) -> None:
        started = handle_agent_run_start(
            {
                "user": "测试品类",
                "default_base_url": "http://127.0.0.1:9",
                "default_api_key": "k",
                "default_model": "m",
            },
            trace_id="t1",
        )
        self.assertTrue(started["ok"])
        run_id = started["run_id"]
        self.assertTrue(run_id)

        time.sleep(0.05)
        cancelled = handle_agent_run_cancel({"run_id": run_id}, trace_id="t1")
        self.assertTrue(cancelled["ok"])
        self.assertEqual(cancelled["state"], "cancelled")

        status = handle_agent_run_status({"run_id": run_id}, trace_id="t1")
        self.assertTrue(status["ok"])
        self.assertEqual(status["state"], "cancelled")

    def test_pause_continue_control(self) -> None:
        run_id = new_run_id()
        initial = build_initial_state("百货")
        run = GraphRun(
            run_id=run_id,
            kind="price_compare",
            user="百货",
            system="",
            initial_state=deep_copy_state(initial),
            state=deep_copy_state(initial),
            node_models={},
            default_model=None,
            steps_order=PRICE_COMPARE_STEPS,
        )
        run.paused.set()
        get_run_registry().create(run)
        threading.Thread(target=run_steps, args=(run,), daemon=True).start()
        time.sleep(0.05)
        resumed = handle_agent_run_control(
            {"run_id": run_id, "action": "continue"},
            trace_id="t",
        )
        self.assertTrue(resumed["ok"])
        handle_agent_run_cancel({"run_id": run_id}, trace_id="t")

    def test_seek_requires_prior_node(self) -> None:
        started = handle_agent_run_start({"user": "x"}, trace_id="t")
        run_id = started["run_id"]
        bad = handle_agent_run_control(
            {"run_id": run_id, "action": "seek", "node": "analyze"},
            trace_id="t",
        )
        self.assertFalse(bad["ok"])
        handle_agent_run_cancel({"run_id": run_id}, trace_id="t")


if __name__ == "__main__":
    unittest.main()
