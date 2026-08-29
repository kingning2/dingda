"""Python → Rust 出站帧队列。

仅 IPC 读循环线程可 ``flush_outbound``（真正 WriteFile）。
其它线程（invoke worker / WSS）只 ``enqueue``，避免 Windows 同步 Named Pipe
上并发 Read+Write 死锁。
"""

from __future__ import annotations

import logging
import queue
from typing import Any, BinaryIO

from dingda_sidecar.runtime.ipc_framing import write_frame

logger = logging.getLogger("dingda.runtime.ipc_push")

_outbound: queue.SimpleQueue[dict[str, Any]] = queue.SimpleQueue()


def bind(_writer: BinaryIO) -> None:
    """兼容旧调用；出站由读循环 ``flush_outbound`` 写出。"""
    # 清空残留，避免跨会话串帧。
    while True:
        try:
            _outbound.get_nowait()
        except queue.Empty:
            break


def unbind() -> None:
    """会话结束；丢弃未刷出站帧。"""
    while True:
        try:
            _outbound.get_nowait()
        except queue.Empty:
            break


def enqueue_message(message: dict[str, Any]) -> None:
    """任意线程安全入队。"""
    _outbound.put(message)


def write_message(message: dict[str, Any]) -> None:
    """入队一帧（由读循环刷出）。"""
    enqueue_message(message)


def flush_outbound(writer: BinaryIO) -> int:
    """仅 IPC 读循环线程调用：写出全部待发帧。对端已断开时静默停止。"""
    count = 0
    while True:
        try:
            message = _outbound.get_nowait()
        except queue.Empty:
            break
        try:
            write_frame(writer, message)
        except OSError as error:
            # 232 ERROR_NO_DATA / broken pipe：对端已关，关闭路径常见。
            logger.debug("出站写失败（对端可能已断开）: %s", error)
            break
        count += 1
    return count


def emit_event(method: str, params: dict[str, Any] | None = None) -> bool:
    """推送 Event（入队）；未绑定会话时仍入队，无读循环则丢弃于 unbind。"""
    try:
        enqueue_message(
            {
                "type": "event",
                "method": method,
                "params": params or {},
            },
        )
        return True
    except Exception:  # noqa: BLE001
        logger.exception("IPC Event 入队失败 method=%s", method)
        return False
