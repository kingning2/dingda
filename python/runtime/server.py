"""Runtime HTTP server — consumed by Rust-managed lifecycle."""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, ClassVar

from runtime.handlers.runtime import build_runtime_status
from runtime.ipc import HANDLERS, ROUTES
from runtime.lifecycle import RuntimeLifecycle
from runtime.observability import get_runtime_observability

logger = logging.getLogger("dingda.runtime")

_QUIET_PATHS = frozenset({"/v1/channel/qr_check"})
_QUIET_SLOW_MS = 500

_ASYNC_LOOP: asyncio.AbstractEventLoop | None = None
_ASYNC_LOOP_LOCK = threading.Lock()


def _duration_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))


def _log_request_completed(
    *,
    path: str,
    status: int,
    duration_ms: int,
    trace_id: str = "",
    handler: str = "",
    ok: bool | None = None,
) -> None:
    extra: dict[str, Any] = {
        "event": "sidecar.request.completed",
        "feature": "runtime",
        "method": "POST",
        "path": path,
        "status": status,
        "duration_ms": duration_ms,
    }
    if handler:
        extra["handler"] = handler
    if trace_id:
        extra["trace_id"] = trace_id
    if ok is not None:
        extra["ok"] = ok
    message = f"接口调用完成 method=POST path={path} status={status} duration_ms={duration_ms}"
    quiet = (
        path in _QUIET_PATHS and status < 400 and duration_ms < _QUIET_SLOW_MS and ok is not False
    )
    if quiet:
        logger.debug(message, extra=extra)
    else:
        logger.info(message, extra=extra)


def _get_async_loop() -> asyncio.AbstractEventLoop:
    global _ASYNC_LOOP
    if _ASYNC_LOOP is None or _ASYNC_LOOP.is_closed():
        with _ASYNC_LOOP_LOCK:
            if _ASYNC_LOOP is None or _ASYNC_LOOP.is_closed():
                loop = asyncio.new_event_loop()

                def _run() -> None:
                    asyncio.set_event_loop(loop)
                    loop.run_forever()

                threading.Thread(target=_run, daemon=True, name="runtime-asyncio").start()
                _ASYNC_LOOP = loop
    return _ASYNC_LOOP


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
        started = time.perf_counter()
        path = self.path
        route = ROUTES.get(path)
        if route is None:
            self._send_json(404, {"code": "not_found", "message": "route not found"})
            _log_request_completed(path=path, status=404, duration_ms=_duration_ms(started))
            return
        method, handler_name = route
        if method != "POST":
            self._send_json(405, {"code": "method_not_allowed", "message": "method not allowed"})
            _log_request_completed(
                path=path,
                status=405,
                duration_ms=_duration_ms(started),
                handler=handler_name,
            )
            return
        handler = HANDLERS.get(handler_name)
        if handler is None:
            self._send_json(500, {"code": "handler_missing", "message": "handler not registered"})
            _log_request_completed(
                path=path,
                status=500,
                duration_ms=_duration_ms(started),
                handler=handler_name,
            )
            return
        payload = self._read_json()
        trace_id = ""
        if isinstance(payload, dict):
            trace_id = str(payload.get("trace_id", ""))
        obs = get_runtime_observability()
        req_op = obs.begin_request(path, handler_name, trace_id)
        try:
            result = handler(payload if isinstance(payload, dict) else None, trace_id=trace_id)
            if inspect.iscoroutine(result):
                loop = _get_async_loop()
                result = asyncio.run_coroutine_threadsafe(result, loop).result()
        except Exception as error:
            duration_ms = _duration_ms(started)
            obs.record_error(path=path, message=str(error), trace_id=trace_id)
            obs.end_request(req_op, ok=False)
            logger.exception(
                "接口调用异常 method=POST path=%s duration_ms=%s",
                path,
                duration_ms,
                extra={
                    "event": "sidecar.request.failed",
                    "feature": "runtime",
                    "method": "POST",
                    "path": path,
                    "status": 500,
                    "duration_ms": duration_ms,
                    "handler": handler_name,
                    "trace_id": trace_id,
                },
            )
            self._send_json(500, {"code": "handler_error", "message": "handler failed"})
            return
        ok: bool | None = None
        if isinstance(result, dict) and "ok" in result:
            ok = bool(result.get("ok"))
            if ok is False:
                message = str(result.get("message") or "handler returned ok=false")
                obs.record_error(path=path, message=message, trace_id=trace_id)
        obs.end_request(req_op, ok=ok)
        self._send_json(200, result)
        _log_request_completed(
            path=path,
            status=200,
            duration_ms=_duration_ms(started),
            trace_id=trace_id,
            handler=handler_name,
            ok=ok,
        )

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
