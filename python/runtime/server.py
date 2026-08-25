"""Runtime HTTP server — 由 Rust 托管生命周期消费。

把 Contract 路径请求交给 ``dispatch_post``；本模块只负责 HTTP 读写与 GET 探活。"""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, ClassVar

from runtime.dispatch import dispatch_post
from runtime.handlers.runtime import build_runtime_status
from runtime.ipc import ROUTES
from runtime.lifecycle import RuntimeLifecycle

logger = logging.getLogger("dingda.runtime")


class RuntimeHandler(BaseHTTPRequestHandler):
    routes: ClassVar[dict[str, tuple[str, str]]] = ROUTES

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json(200, {"status": "ok"})
            return
        if self.path == "/v1/runtime/status":
            self._send_json(200, build_runtime_status())
            return
        if self.path == "/stats":
            self._send_json(200, {"uptime_ms": 0, "requests": 0})
            return
        if self.path == "/tasks/active":
            self._send_json(200, {"tasks": []})
            return
        if self.path == "/debug/dump":
            self._send_json(200, {"routes": list(ROUTES.keys())})
            return
        if self.path == "/metrics":
            self._send_text(200, "# dingda runtime metrics (skeleton)\n")
            return
        self._send_json(404, {"code": "not_found", "message": "route not found"})

    def do_POST(self) -> None:
        payload = self._read_json()
        body = payload if isinstance(payload, dict) else None
        result = dispatch_post(self.path, body, method="POST")
        self._send_json(result.status, result.body)

    def _read_json(self) -> Any:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            return None
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, status: int, payload: str) -> None:
        body = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve(port: int = 8787) -> None:
    lifecycle = RuntimeLifecycle()
    lifecycle.on_starting()

    host = "127.0.0.1"
    server = ThreadingHTTPServer((host, port), RuntimeHandler)
    bind_host, bind_port = server.server_address
    base_url = f"http://{bind_host}:{bind_port}"
    health_url = f"{base_url}/health"
    routes = ["/health", "/stats", *sorted(ROUTES)]
    lifecycle.on_ready()
    lifecycle.on_running()

    logger.info(
        "python端http服务启动 base_url=%s",
        base_url,
        extra={
            "event": "sidecar.starting",
            "feature": "runtime",
            "host": bind_host,
            "port": bind_port,
            "base_url": base_url,
            "health_url": health_url,
            "routes": routes,
        },
    )
    try:
        server.serve_forever()
    except Exception:
        logger.exception(
            "侧车服务异常",
            extra={"event": "sidecar.failed", "feature": "runtime"},
        )
        raise
    finally:
        lifecycle.on_stopping()
        server.server_close()
        lifecycle.on_stopped()
