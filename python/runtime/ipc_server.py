"""跨平台 IPC 监听端 — Windows Named Pipe / Unix Domain Socket。

Python 作为 server 监听，Rust 作为 client 连接；连接后发送 ``runtime.ready``，
再进入请求循环。复用 ``dispatch_post`` 处理 ``sidecar.invoke``。
"""

from __future__ import annotations

import logging
import os
import socket
import sys
import threading
from typing import Any, BinaryIO

from runtime.dispatch import dispatch_post
from runtime.handlers.runtime import build_runtime_status
from runtime.ipc_framing import read_frame, write_frame
from runtime.observability import RuntimeState, get_runtime_observability

logger = logging.getLogger("dingda.runtime.ipc")


def serve_ipc(endpoint: str) -> None:
    """阻塞监听 IPC，直到 shutdown / 连接断开。"""
    if sys.platform == "win32":
        _serve_named_pipe(endpoint)
    else:
        _serve_unix_socket(endpoint)


def _serve_unix_socket(path: str) -> None:
    if os.path.exists(path):
        os.unlink(path)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(path)
    server.listen(1)
    logger.info(
        "IPC Unix socket 监听 path=%s",
        path,
        extra={"event": "sidecar.ipc.listening", "feature": "runtime", "ipc": path},
    )
    try:
        conn, _addr = server.accept()
    finally:
        server.close()
    with conn:
        reader = conn.makefile("rb")
        writer = conn.makefile("wb")
        try:
            _session_loop(reader, writer)
        finally:
            reader.close()
            writer.close()


def _serve_named_pipe(name: str) -> None:
    """Windows Named Pipe server（ctypes）。"""
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    PIPE_ACCESS_DUPLEX = 0x00000003  # noqa: N806
    PIPE_TYPE_BYTE = 0x00000000  # noqa: N806
    PIPE_READMODE_BYTE = 0x00000000  # noqa: N806
    PIPE_WAIT = 0x00000000  # noqa: N806
    ERROR_PIPE_CONNECTED = 535  # noqa: N806
    INVALID_HANDLE_VALUE = (  # noqa: N806
        0xFFFFFFFFFFFFFFFF if ctypes.sizeof(ctypes.c_void_p) == 8 else 0xFFFFFFFF
    )

    CreateNamedPipeW = kernel32.CreateNamedPipeW  # noqa: N806
    CreateNamedPipeW.argtypes = [  # noqa: N806
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
    ]
    CreateNamedPipeW.restype = wintypes.HANDLE  # noqa: N806

    ConnectNamedPipe = kernel32.ConnectNamedPipe  # noqa: N806
    ConnectNamedPipe.argtypes = [wintypes.HANDLE, wintypes.LPVOID]  # noqa: N806
    ConnectNamedPipe.restype = wintypes.BOOL  # noqa: N806

    GetLastError = kernel32.GetLastError  # noqa: N806
    GetLastError.restype = wintypes.DWORD  # noqa: N806

    handle = CreateNamedPipeW(
        name,
        PIPE_ACCESS_DUPLEX,
        PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
        1,
        64 * 1024,
        64 * 1024,
        0,
        None,
    )
    if not handle or int(handle) == INVALID_HANDLE_VALUE:
        raise OSError(f"CreateNamedPipeW failed for {name}: {ctypes.get_last_error()}")

    logger.info(
        "IPC Named Pipe 监听 name=%s",
        name,
        extra={"event": "sidecar.ipc.listening", "feature": "runtime", "ipc": name},
    )
    ok = ConnectNamedPipe(handle, None)
    if not ok and GetLastError() != ERROR_PIPE_CONNECTED:
        kernel32.CloseHandle(handle)
        raise OSError(f"ConnectNamedPipe failed: {GetLastError()}")

    pipe = _WinPipeIO(int(handle))
    try:
        _session_loop(pipe, pipe)
    finally:
        pipe.close()


class _WinPipeIO:
    """基于同一 Named Pipe HANDLE 的读写包装。"""

    def __init__(self, handle: int) -> None:
        import ctypes
        from ctypes import wintypes

        self._handle = handle
        self._kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._ReadFile = self._kernel32.ReadFile
        self._ReadFile.argtypes = [
            wintypes.HANDLE,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        ]
        self._ReadFile.restype = wintypes.BOOL
        self._WriteFile = self._kernel32.WriteFile
        self._WriteFile.argtypes = [
            wintypes.HANDLE,
            wintypes.LPCVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.LPVOID,
        ]
        self._WriteFile.restype = wintypes.BOOL
        self._CloseHandle = self._kernel32.CloseHandle
        self._closed = False

    def read(self, n: int) -> bytes:
        if self._closed or n <= 0:
            return b""
        import ctypes
        from ctypes import wintypes

        buf = ctypes.create_string_buffer(n)
        read = wintypes.DWORD(0)
        ok = self._ReadFile(self._handle, buf, n, ctypes.byref(read), None)
        if not ok or read.value == 0:
            return b""
        return buf.raw[: read.value]

    def write(self, data: bytes) -> int:
        if self._closed:
            return 0
        import ctypes
        from ctypes import wintypes

        written = wintypes.DWORD(0)
        ok = self._WriteFile(self._handle, data, len(data), ctypes.byref(written), None)
        if not ok:
            raise OSError(f"WriteFile failed: {ctypes.get_last_error()}")
        return int(written.value)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        if not self._closed:
            self._closed = True
            self._CloseHandle(self._handle)


def _session_loop(reader: BinaryIO, writer: BinaryIO) -> None:
    obs = get_runtime_observability()
    obs.set_state(RuntimeState.RUNNING)
    write_frame(writer, {"type": "event", "method": "runtime.ready", "params": {}})
    logger.info(
        "IPC 已连接并发送 runtime.ready",
        extra={"event": "sidecar.ready", "feature": "runtime"},
    )

    stop = threading.Event()

    while not stop.is_set():
        try:
            message = read_frame(reader)
        except Exception:
            logger.exception("IPC 读帧失败")
            break
        if message is None:
            logger.info("IPC 对端关闭", extra={"event": "sidecar.ipc.closed", "feature": "runtime"})
            break
        if message.get("type") != "request":
            logger.warning("忽略非 request 消息 type=%s", message.get("type"))
            continue

        req_id = int(message.get("id") or 0)
        method = str(message.get("method") or "")
        params = message.get("params")
        if not isinstance(params, dict):
            params = {}

        try:
            result = _dispatch_method(method, params, stop)
            write_frame(
                writer,
                {"type": "response", "id": req_id, "success": True, "result": result},
            )
        except _ShutdownSignal:
            write_frame(
                writer,
                {"type": "response", "id": req_id, "success": True, "result": {"ok": True}},
            )
            stop.set()
            break
        except Exception as error:
            logger.exception("IPC handler 失败 method=%s", method)
            write_frame(
                writer,
                {
                    "type": "response",
                    "id": req_id,
                    "success": False,
                    "error": {"code": "handler_error", "message": str(error)},
                },
            )


class _ShutdownSignal(Exception):  # noqa: N818
    pass


def _dispatch_method(method: str, params: dict[str, Any], stop: threading.Event) -> Any:
    if method == "runtime.ping":
        return {"pong": True}
    if method == "runtime.shutdown":
        stop.set()
        raise _ShutdownSignal()
    if method == "sidecar.invoke":
        return _invoke_http(params)
    raise ValueError(f"unknown method: {method}")


def _invoke_http(params: dict[str, Any]) -> dict[str, Any]:
    http_method = str(params.get("http_method") or "POST").upper()
    path = str(params.get("path") or "")
    body = params.get("body")

    if http_method == "GET":
        if path == "/health":
            return {"status": 200, "body": {"status": "ok"}}
        if path == "/v1/runtime/status":
            return {"status": 200, "body": build_runtime_status()}
        if path == "/stats":
            return {"status": 200, "body": {"uptime_ms": 0, "requests": 0}}
        return {"status": 404, "body": {"code": "not_found", "message": "route not found"}}

    if path == "/v1/system/shutdown":
        raise _ShutdownSignal()

    payload = body if isinstance(body, dict) else None
    result = dispatch_post(path, payload, method=http_method)
    return {"status": result.status, "body": result.body}
