"""产品 pipe IPC — 业务 ``sidecar.invoke`` + Event 推送。

无 SHM：请求/响应与 ``ws.event`` 均走 Named Pipe / Unix Socket。

Windows 同步 Named Pipe 禁止多线程并发 Read+Write：本模块由读循环独占 I/O，
出站经 ``ipc_push`` 队列刷出；invoke 可进线程池，只负责入队响应。
"""

from __future__ import annotations

import contextlib
import logging
import os
import select
import socket
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, BinaryIO, Protocol

from dingda_sidecar.runtime.dispatch import dispatch_post
from dingda_sidecar.runtime.handlers.runtime import build_runtime_status
from dingda_sidecar.runtime.ipc_framing import read_frame
from dingda_sidecar.runtime.ipc_push import bind as bind_ipc_writer
from dingda_sidecar.runtime.ipc_push import flush_outbound, write_message
from dingda_sidecar.runtime.ipc_push import unbind as unbind_ipc_writer

logger = logging.getLogger("dingda.runtime.ipc")

_INVOKE_WORKERS = 8
_IDLE_POLL_SEC = 0.02


class _Readable(Protocol):
    def wait_readable(self, timeout_sec: float) -> bool: ...


def serve_ipc(endpoint: str) -> None:
    """产品入口：仅 pipe（无 SHM）。"""
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
        "Pipe Unix socket 监听 path=%s",
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
            _session_loop(reader, writer, _UnixReadable(conn))
        finally:
            reader.close()
            writer.close()


def _serve_named_pipe(name: str) -> None:
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    PIPE_ACCESS_DUPLEX = 0x00000003  # noqa: N806
    PIPE_TYPE_BYTE = 0x00000000  # noqa: N806
    PIPE_READMODE_BYTE = 0x00000000  # noqa: N806
    PIPE_WAIT = 0x00000000  # noqa: N806
    ERROR_PIPE_CONNECTED = 535  # noqa: N806
    ERROR_PIPE_BUSY = 231  # noqa: N806
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

    handle = None
    last_error = 0
    for _ in range(40):
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
        if handle and int(handle) != INVALID_HANDLE_VALUE:
            break
        last_error = int(GetLastError())
        handle = None
        if last_error != ERROR_PIPE_BUSY:
            break
        # 旧实例尚未释放：短暂重试，避免热重启 ERROR_PIPE_BUSY。
        time.sleep(0.05)
    if handle is None or int(handle) == INVALID_HANDLE_VALUE:
        raise OSError(f"CreateNamedPipeW failed for {name}: {last_error or GetLastError()}")
    logger.info(
        "Pipe Named Pipe 监听 name=%s",
        name,
        extra={"event": "sidecar.ipc.listening", "feature": "runtime", "ipc": name},
    )
    ok = ConnectNamedPipe(handle, None)
    if not ok and GetLastError() != ERROR_PIPE_CONNECTED:
        kernel32.CloseHandle(handle)
        raise OSError(f"ConnectNamedPipe failed: {GetLastError()}")
    pipe = _WinPipeIO(int(handle))
    try:
        _session_loop(pipe, pipe, pipe)
    finally:
        pipe.close()


class _UnixReadable:
    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock

    def wait_readable(self, timeout_sec: float) -> bool:
        ready, _, _ = select.select([self._sock], [], [], timeout_sec)
        return bool(ready)


class _WinPipeIO:
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
        self._PeekNamedPipe = self._kernel32.PeekNamedPipe
        self._PeekNamedPipe.argtypes = [
            wintypes.HANDLE,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
            ctypes.POINTER(wintypes.DWORD),
        ]
        self._PeekNamedPipe.restype = wintypes.BOOL
        self._CloseHandle = self._kernel32.CloseHandle
        self._closed = False

    def wait_readable(self, timeout_sec: float) -> bool:
        deadline = time.monotonic() + timeout_sec
        while True:
            if self._bytes_available() > 0:
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.005)

    def _bytes_available(self) -> int:
        if self._closed:
            return 0
        import ctypes
        from ctypes import wintypes

        avail = wintypes.DWORD(0)
        ok = self._PeekNamedPipe(
            self._handle,
            None,
            0,
            None,
            ctypes.byref(avail),
            None,
        )
        if not ok:
            return 0
        return int(avail.value)

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


def _session_loop(reader: BinaryIO, writer: BinaryIO, readable: _Readable) -> None:
    from dingda_sidecar.runtime.lifecycle import RuntimeLifecycle

    lifecycle = RuntimeLifecycle()
    lifecycle.on_starting()
    bind_ipc_writer(writer)
    executor = ThreadPoolExecutor(max_workers=_INVOKE_WORKERS, thread_name_prefix="pipe-invoke")
    stop = threading.Event()
    try:
        lifecycle.on_ready()
        lifecycle.on_running()
        write_message({"type": "event", "method": "runtime.ready", "params": {}})
        flush_outbound(writer)
        logger.info(
            "Pipe IPC 已连接并发送 runtime.ready",
            extra={"event": "sidecar.ready", "feature": "runtime"},
        )

        while not stop.is_set():
            flush_outbound(writer)
            if not readable.wait_readable(_IDLE_POLL_SEC):
                continue
            try:
                message = read_frame(reader)
            except Exception:
                logger.exception("IPC 读帧失败")
                break
            if message is None:
                logger.info(
                    "IPC 对端关闭",
                    extra={"event": "sidecar.ipc.closed", "feature": "runtime"},
                )
                break
            if message.get("type") != "request":
                logger.warning("忽略非 request 消息 type=%s", message.get("type"))
                continue

            req_id = int(message.get("id") or 0)
            method = str(message.get("method") or "")
            params = message.get("params")
            if not isinstance(params, dict):
                params = {}

            if method == "sidecar.invoke":
                executor.submit(_run_invoke, req_id, params)
                continue

            try:
                result = _dispatch_control(method, stop)
                write_message(
                    {"type": "response", "id": req_id, "success": True, "result": result},
                )
            except _ShutdownSignal:
                write_message(
                    {"type": "response", "id": req_id, "success": True, "result": {"ok": True}},
                )
                flush_outbound(writer)
                stop.set()
                break
            except Exception as error:
                logger.exception("IPC control handler 失败 method=%s", method)
                write_message(
                    {
                        "type": "response",
                        "id": req_id,
                        "success": False,
                        "error": {"code": "handler_error", "message": str(error)},
                    },
                )
            flush_outbound(writer)
    finally:
        stop.set()
        executor.shutdown(wait=False, cancel_futures=True)
        with contextlib.suppress(Exception):
            flush_outbound(writer)
        unbind_ipc_writer()
        lifecycle.on_stopping()
        lifecycle.on_stopped()


def _run_invoke(req_id: int, params: dict[str, Any]) -> None:
    try:
        result = _handle_invoke(params)
        write_message(
            {"type": "response", "id": req_id, "success": True, "result": result},
        )
    except Exception as error:  # noqa: BLE001
        logger.exception("sidecar.invoke 失败 id=%s", req_id)
        write_message(
            {
                "type": "response",
                "id": req_id,
                "success": False,
                "error": {"code": "handler_error", "message": str(error)},
            },
        )


def _handle_invoke(params: dict[str, Any]) -> dict[str, Any]:
    method = str(params.get("method") or "POST").upper()
    path = str(params.get("path") or "")
    body = params.get("body")

    if method == "GET":
        if path == "/health":
            return {"status": 200, "body": {"status": "ok"}}
        if path == "/v1/runtime/status":
            return {"status": 200, "body": build_runtime_status()}
        return {
            "status": 404,
            "body": {"code": "not_found", "message": "route not found"},
        }

    if method == "POST":
        if path == "/v1/system/shutdown":
            return {"status": 200, "body": {"ok": True}}
        payload = body if isinstance(body, dict) else None
        dispatched = dispatch_post(path, payload, method=method)
        return {"status": dispatched.status, "body": dispatched.body}

    return {
        "status": 405,
        "body": {"code": "method_not_allowed", "message": "method not allowed"},
    }


class _ShutdownSignal(Exception):  # noqa: N818
    pass


def _dispatch_control(method: str, stop: threading.Event) -> Any:
    if method == "runtime.ping":
        return {"pong": True}
    if method == "runtime.shutdown":
        stop.set()
        raise _ShutdownSignal()
    if method == "shm.wake":
        raise ValueError("shm.wake 需要 hybrid --shm + --ipc；产品路径为 pipe-only")
    raise ValueError(f"unknown method: {method}")
