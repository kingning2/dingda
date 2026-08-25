"""HTTP / 共享内存共用的 POST 请求分发。

查 ROUTES → 调 HANDLERS → 记 observability → 返回 status/body。
传输层只负责读写（HTTP 响应头 / SHM 槽位），不重复分发逻辑。
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any

from runtime.ipc import HANDLERS, ROUTES
from runtime.observability import get_runtime_observability

logger = logging.getLogger("dingda.runtime.dispatch")

_QUIET_PATHS = frozenset({"/v1/channel/qr_check"})
_QUIET_SLOW_MS = 500

_ASYNC_LOOP: asyncio.AbstractEventLoop | None = None
_ASYNC_LOOP_LOCK = threading.Lock()


@dataclass(frozen=True)
class DispatchResult:
    """统一分发结果 — 传输层据此写回 HTTP / SHM 响应。"""

    status: int
    body: dict[str, Any]
    handler: str = ""
    trace_id: str = ""
    ok: bool | None = None


def duration_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))


def log_request_completed(
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


def get_async_loop() -> asyncio.AbstractEventLoop:
    """供 sync 传输线程执行 async handler 的后台事件循环。"""
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


def dispatch_post(
    path: str,
    body: dict[str, Any] | None,
    *,
    method: str = "POST",
) -> DispatchResult:
    """分发一条契约 POST（或方法校验失败）请求。"""
    started = time.perf_counter()
    trace_id = ""
    if isinstance(body, dict):
        trace_id = str(body.get("trace_id", ""))

    route = ROUTES.get(path)
    if route is None:
        result = DispatchResult(
            status=404,
            body={"code": "not_found", "message": "route not found"},
            trace_id=trace_id,
        )
        log_request_completed(
            path=path,
            status=result.status,
            duration_ms=duration_ms(started),
            trace_id=trace_id,
        )
        return result

    expected_method, handler_name = route
    if method != expected_method:
        result = DispatchResult(
            status=405,
            body={"code": "method_not_allowed", "message": "method not allowed"},
            handler=handler_name,
            trace_id=trace_id,
        )
        log_request_completed(
            path=path,
            status=result.status,
            duration_ms=duration_ms(started),
            trace_id=trace_id,
            handler=handler_name,
        )
        return result

    handler = HANDLERS.get(handler_name)
    if handler is None:
        result = DispatchResult(
            status=500,
            body={"code": "handler_missing", "message": "handler not registered"},
            handler=handler_name,
            trace_id=trace_id,
        )
        log_request_completed(
            path=path,
            status=result.status,
            duration_ms=duration_ms(started),
            trace_id=trace_id,
            handler=handler_name,
        )
        return result

    obs = get_runtime_observability()
    req_op = obs.begin_request(path, handler_name, trace_id)
    try:
        payload = handler(body if isinstance(body, dict) else None, trace_id=trace_id)
        if inspect.iscoroutine(payload):
            loop = get_async_loop()
            payload = asyncio.run_coroutine_threadsafe(payload, loop).result()
    except Exception as error:
        elapsed = duration_ms(started)
        obs.record_error(path=path, message=str(error), trace_id=trace_id)
        obs.end_request(req_op, ok=False)
        logger.exception(
            "接口调用异常 method=%s path=%s duration_ms=%s",
            method,
            path,
            elapsed,
            extra={
                "event": "sidecar.request.failed",
                "feature": "runtime",
                "method": method,
                "path": path,
                "status": 500,
                "duration_ms": elapsed,
                "handler": handler_name,
                "trace_id": trace_id,
            },
        )
        result = DispatchResult(
            status=500,
            body={"code": "handler_error", "message": "handler failed"},
            handler=handler_name,
            trace_id=trace_id,
            ok=False,
        )
        return result

    if not isinstance(payload, dict):
        payload = {"result": payload}

    ok: bool | None = None
    if "ok" in payload:
        ok = bool(payload.get("ok"))
        if ok is False:
            message = str(payload.get("message") or "handler returned ok=false")
            obs.record_error(path=path, message=message, trace_id=trace_id)
    obs.end_request(req_op, ok=ok)

    result = DispatchResult(
        status=200,
        body=payload,
        handler=handler_name,
        trace_id=trace_id,
        ok=ok,
    )
    log_request_completed(
        path=path,
        status=result.status,
        duration_ms=duration_ms(started),
        trace_id=trace_id,
        handler=handler_name,
        ok=ok,
    )
    return result
