"""Runtime observability 单元测试。

验证活跃操作登记、错误记录与状态快照字段。"""

from __future__ import annotations

import unittest

from runtime.observability import RuntimeObservability, RuntimeState, track_workflow


class RuntimeObservabilityTests(unittest.TestCase):
    def test_snapshot_includes_active_ops_and_errors(self) -> None:
        obs = RuntimeObservability()
        obs.set_state(RuntimeState.RUNNING)
        op_id = obs.begin_op("buyer_reply", detail="cid=abc", stage="graph")
        obs.record_error(path="/v1/agent/reply", message="boom", trace_id="t1")
        snap = obs.snapshot()
        self.assertTrue(snap["ok"])
        self.assertEqual(snap["state"], "running")
        self.assertEqual(len(snap["active_ops"]), 1)
        self.assertEqual(snap["active_ops"][0]["kind"], "buyer_reply")
        self.assertEqual(snap["recent_errors"][0]["message"], "boom")
        obs.end_op(op_id)

    def test_track_workflow_context_manager(self) -> None:
        from runtime.observability import get_runtime_observability

        obs = get_runtime_observability()
        with track_workflow("agent_reply", detail="trace-1") as run:
            run.stage("price_compare")
            self.assertEqual(len(obs.snapshot()["active_ops"]), 1)
        self.assertEqual(len(obs.snapshot()["active_ops"]), 0)


if __name__ == "__main__":
    unittest.main()
