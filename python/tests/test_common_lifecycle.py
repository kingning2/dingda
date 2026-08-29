"""Component ABC 契约 — 状态机与 supervisor 聚合行为。"""

from __future__ import annotations

import unittest
from typing import Any

from dingda_sidecar.common.lifecycle import Component
from dingda_sidecar.runtime.context import RuntimeContext


class _Dummy(Component):
    name = "dummy"

    def __init__(self) -> None:
        self._calls: list[str] = []

    def start(self, ctx: RuntimeContext) -> None:
        self._calls.append("start")
        self.mark_started()

    def stop(self) -> None:
        self._calls.append("stop")
        self.mark_stopped()

    def status(self) -> dict[str, Any]:
        return {"name": self.name}


class TestComponent(unittest.TestCase):
    def test_state_transitions(self) -> None:
        c = _Dummy()
        self.assertEqual(c.state(), "stopped")
        c.start(RuntimeContext(app=None))
        self.assertEqual(c.state(), "running")
        c.stop()
        self.assertEqual(c.state(), "stopped")

    def test_start_is_idempotent_shape(self) -> None:
        c = _Dummy()
        c.start(RuntimeContext(app=None))
        c.start(RuntimeContext(app=None))
        self.assertEqual(c._calls.count("start"), 2)  # 幂等由子类保证；契约仅记录调用
        self.assertEqual(c.state(), "running")


if __name__ == "__main__":
    unittest.main()
