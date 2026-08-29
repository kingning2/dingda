"""Hybrid sidecar — SHM 载荷 + Named Pipe / Unix Socket 唤醒。

启动顺序：打开 Rust 已创建的 SHM → ready/心跳 → 监听 pipe →
连接后发 ``runtime.ready`` → 收到 ``shm.wake`` 处理对应槽位。
"""

from __future__ import annotations

import contextlib
import logging
import os
import socket
import sys
import threading
from typing import Any, BinaryIO

from dingda_sidecar.runtime.ipc_framing import read_frame
from dingda_sidecar.runtime.ipc_push import bind as bind_ipc_writer
from dingda_sidecar.runtime.ipc_push import flush_outbound, write_message
from dingda_sidecar.runtime.ipc_push import unbind as unbind_ipc_writer
from dingda_sidecar.runtime.observability import RuntimeState, get_runtime_observability
from dingda_sidecar.runtime.shm_server import ShmServer

logger = logging.getLogger("dingda.runtime.hybrid")


def serve_hybrid(shm_path: str, ipc_endpoint: str) -> None:
    """阻塞运行 hybrid 服务直到 shutdown / 连接断开。"""
    server = ShmServer(shm_path)
    server.bootstrap()
    try:
        if sys.platform == "win32":
            _serve_named_pipe(ipc_endpoint, server)
        else:
            _serve_unix_socket(ipc_endpoint, server)
    finally:
        server.stop()


def _serve_unix_socket(path: str, server: ShmServer) -> None:
    if os.path.exists(path):
        os.unlink(path)
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.bind(path)
    sock.listen(1)
    logger.info(
        "Hybrid Unix socket 监听 path=%s",
        path,
        extra={"event": "sidecar.ipc.listening", "feature": "runtime", "ipc": path},
    )
    try:
        conn, _addr = sock.accept()
    finally:
        sock.close()
    with conn:
        reader = conn.makefile("rb")
        writer = conn.makefile("wb")
        try:
            _control_loop(reader, writer, server)
        finally:
            reader.close()
            writer.close()


def _serve_named_pipe(name: str, server: ShmServer) -> None:
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
        "Hybrid Named Pipe 监听 name=%s",
        name,
        extra={"event": "sidecar.ipc.listening", "feature": "runtime", "ipc": name},
    )
    ok = ConnectNamedPipe(handle, None)
    if not ok and GetLastError() != ERROR_PIPE_CONNECTED:
        kernel32.CloseHandle(handle)
        raise OSError(f"ConnectNamedPipe failed: {GetLastError()}")

    pipe = _WinPipeIO(int(handle))
    try:
        _control_loop(pipe, pipe, server)
    finally:
        pipe.close()


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


def _control_loop(reader: BinaryIO, writer: BinaryIO, server: ShmServer) -> None:
    obs = get_runtime_observability()
    obs.set_state(RuntimeState.RUNNING)
    bind_ipc_writer(writer)
    try:
        write_message({"type": "event", "method": "runtime.ready", "params": {}})
        flush_outbound(writer)
        logger.info(
            "Hybrid IPC 已连接并发送 runtime.ready",
            extra={"event": "sidecar.ready", "feature": "runtime"},
        )

        stop = threading.Event()
        fallback = threading.Thread(
            target=_fallback_scan_loop,
            args=(server, stop),
            daemon=True,
            name="shm-fallback-scan",
        )
        fallback.start()

        while not stop.is_set() and not server.is_stopped():
            flush_outbound(writer)
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

            try:
                result = _dispatch_control(method, params, server, stop)
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

        stop.set()
        server.stop()
    finally:
        with contextlib.suppress(Exception):
            flush_outbound(writer)
        unbind_ipc_writer()


def _fallback_scan_loop(server: ShmServer, stop: threading.Event) -> None:
    """低频兜底扫描，防止 wake 丢失。"""
    while not stop.is_set() and not server.is_stopped():
        server.scan_slots()
        stop.wait(0.2)


def _dispatch_control(
    method: str,
    params: dict[str, Any],
    server: ShmServer,
    stop: threading.Event,
) -> Any:
    if method == "runtime.ping":
        return {"pong": True}
    if method == "runtime.shutdown":
        stop.set()
        raise _ShutdownSignal()
    if method == "shm.wake":
        slot = params.get("slot")
        if isinstance(slot, int):
            server.wake_slot(slot)
        else:
            server.scan_slots()
        return {"ok": True}
    if method == "sidecar.invoke":
        raise ValueError("sidecar.invoke 已停用；业务请走共享内存载荷")
    raise ValueError(f"unknown control method: {method}")


class _ShutdownSignal(Exception):  # noqa: N818
    pass
