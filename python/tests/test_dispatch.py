"""dispatch_post 单元测试 — 404 / 405 / 成功路径。"""

from __future__ import annotations

import unittest

from dingda_sidecar.runtime import dispatch as dispatch_mod
from dingda_sidecar.runtime.dispatch import dispatch_post
from dingda_sidecar.runtime.ipc import HANDLERS, ROUTES


class DispatchPostTests(unittest.TestCase):
    def test_unknown_path_returns_404(self) -> None:
        result = dispatch_post("/v1/does/not/exist", {"trace_id": "t-404"})
        self.assertEqual(result.status, 404)
        self.assertEqual(result.body["code"], "not_found")
        self.assertEqual(result.trace_id, "t-404")

    def test_wrong_method_returns_405(self) -> None:
        path = next(iter(ROUTES))
        result = dispatch_post(path, {"trace_id": "t-405"}, method="GET")
        self.assertEqual(result.status, 405)
        self.assertEqual(result.body["code"], "method_not_allowed")
        self.assertEqual(result.handler, ROUTES[path][1])
        self.assertEqual(result.trace_id, "t-405")

    def test_success_invokes_handler(self) -> None:
        path = "/v1/__dispatch_test__"
        handler_name = "handle_dispatch_test"
        ROUTES[path] = ("POST", handler_name)
        HANDLERS[handler_name] = lambda body, trace_id="": {
            "ok": True,
            "echo": (body or {}).get("x"),
            "trace_id": trace_id,
        }
        try:
            result = dispatch_post(path, {"x": 42, "trace_id": "t-ok"})
            self.assertEqual(result.status, 200)
            self.assertEqual(result.body["ok"], True)
            self.assertEqual(result.body["echo"], 42)
            self.assertEqual(result.handler, handler_name)
            self.assertEqual(result.ok, True)
        finally:
            ROUTES.pop(path, None)
            HANDLERS.pop(handler_name, None)

    def test_handler_exception_returns_500(self) -> None:
        path = "/v1/__dispatch_boom__"
        handler_name = "handle_dispatch_boom"
        ROUTES[path] = ("POST", handler_name)

        def _boom(body, trace_id=""):  # noqa: ARG001
            raise RuntimeError("boom")

        HANDLERS[handler_name] = _boom
        try:
            with self.assertLogs(dispatch_mod.logger, level="ERROR"):
                result = dispatch_post(path, {"trace_id": "t-err"})
            self.assertEqual(result.status, 500)
            self.assertEqual(result.body["code"], "handler_error")
            self.assertEqual(result.ok, False)
        finally:
            ROUTES.pop(path, None)
            HANDLERS.pop(handler_name, None)


if __name__ == "__main__":
    unittest.main()
