"""Runtime HTTP server — 由 Rust 托管生命周期消费。

把 Contract 路径请求交给 ``dispatch_post``；本模块只负责 HTTP 读写与 GET 探活。
另承载副驾直连 SSE 端点（``/v1/copilot/agui``，前端 CopilotKit 例外直连，
见 contracts/schema/v1/copilot/AG_UI_MAPPING.md）与辅助 HTTP 服务。"""

from __future__ import annotations

import json
import logging
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, ClassVar

from dingda_sidecar.runtime.dispatch import dispatch_post
from dingda_sidecar.runtime.handlers.runtime import build_runtime_status
from dingda_sidecar.runtime.ipc import ROUTES
from dingda_sidecar.runtime.lifecycle import RuntimeLifecycle

logger = logging.getLogger("dingda.runtime")

COPILOT_SSE_PATH = "/v1/copilot/agui"

_copilot_http_port: int | None = None
_copilot_http_lock = threading.Lock()


class RuntimeHandler(BaseHTTPRequestHandler):
    routes: ClassVar[dict[str, tuple[str, str]]] = ROUTES

    def log_message(self, format: str, *args: object) -> None:
        del format, args

    def do_OPTIONS(self) -> None:
        path = self.path.split("?")[0]
        if path == COPILOT_SSE_PATH:
            self.send_response(204)
            self._send_cors_headers()
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()

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
        path = self.path.split("?")[0]
        if path == COPILOT_SSE_PATH:
            self._handle_copilot_sse()
            return
        payload = self._read_json()
        body = payload if isinstance(payload, dict) else None
        result = dispatch_post(self.path, body, method="POST")
        self._send_json(result.status, result.body)

    def _handle_copilot_sse(self) -> None:
        """副驾直连 SSE：请求体为 AG-UI RunAgentInput，响应为 AG-UI 事件流。"""
        from dingda_sidecar.runtime.handlers.copilot import (
            abort_copilot_stream,
            start_copilot_stream,
        )

        try:
            payload = self._read_json()
        except Exception:  # noqa: BLE001
            self._send_json(400, {"code": "bad_request", "message": "invalid json body"})
            return
        stream = start_copilot_stream(payload if isinstance(payload, dict) else {})

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self._send_cors_headers()
        self.end_headers()
        try:
            while True:
                try:
                    event = stream.events.get(timeout=1.0)
                except queue.Empty:
                    if stream.done.is_set():
                        break
                    # 心跳保活，防连接空闲被提前断开。
                    self.wfile.write(b": ping\n\n")
                    self.wfile.flush()
                    continue
                frame = f"data: {json.dumps(event, ensure_ascii=False)}\n\n".encode()
                self.wfile.write(frame)
                self.wfile.flush()
                if event.get("type") in ("RUN_FINISHED", "RUN_ERROR"):
                    break
        except (BrokenPipeError, ConnectionResetError, OSError):
            logger.info(
                "copilot SSE 客户端断开 run_id=%s",
                stream.run_id,
                extra={"run_id": stream.run_id, "feature": "copilot"},
            )
        finally:
            abort_copilot_stream(stream)

    def _send_cors_headers(self) -> None:
        """WebView 直连副驾 SSE 为跨域 fetch，须回显 Origin 并允许预检。"""
        origin = self.headers.get("Origin")
        self.send_header("Access-Control-Allow-Origin", origin or "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept")
        self.send_header("Access-Control-Max-Age", "86400")

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


def copilot_http_port() -> int | None:
    """副驾直连 HTTP 服务端口；未启动时为 None（经 pipe /v1/copilot/http_info 暴露）。"""
    return _copilot_http_port


def start_copilot_http_server() -> int:
    """启动副驾直连 HTTP 服务（127.0.0.1 随机端口，daemon 线程）；幂等。

    产品 pipe 模式（``serve_ipc``）启动时调用，供前端 CopilotKit 直连。
    """
    global _copilot_http_port
    with _copilot_http_lock:
        if _copilot_http_port is not None:
            return _copilot_http_port
        server = ThreadingHTTPServer(("127.0.0.1", 0), RuntimeHandler)
        _copilot_http_port = int(server.server_address[1])
        threading.Thread(
            target=server.serve_forever,
            name="copilot-http",
            daemon=True,
        ).start()
    logger.info(
        "copilot 直连 HTTP 已启动 port=%s",
        _copilot_http_port,
        extra={
            "event": "sidecar.copilot_http.ready",
            "feature": "copilot",
            "port": _copilot_http_port,
        },
    )
    return _copilot_http_port


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
