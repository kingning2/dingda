"""共享内存服务端（Python 写端）— 由 Rust 通过 `--shm` 启动时启用。

与 Rust `ShmTransport`（`core/manager/python/shm/transport.rs`）
逐字段对齐：Python 在就绪后置 `ready=1` 并周期性刷新心跳；单调度线程扫描
槽位认领 `REQ_READY` 请求，提交到线程池执行，完成后写回响应并置 `RES_READY`。
Rust 侧读取响应后自行归位 `IDLE`。启动时将所有槽位置 `IDLE`，供 Rust 侧
"Sidecar 重启" 检测使用。

请求 envelope（与 Rust `client.rs` 一致）:
```json
{ "method": "POST", "path": "/v1/...", "body": {...} }
```
路由分发复用 `runtime.ipc.ROUTES / HANDLERS`，handler 签名与 HTTP 版本相同：
`handler(payload, trace_id=...)`，可返回 `dict` 或协程。
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import mmap
import os
import struct
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from runtime import shm_protocol as shm
from runtime.ipc import HANDLERS, ROUTES
from runtime.observability import get_runtime_observability
from runtime.server import _get_async_loop

logger = logging.getLogger("dingda.runtime.shm")

_QUIET_PATHS = frozenset({"/v1/channel/qr_check"})
_QUIET_SLOW_MS = 500

# 心跳刷新周期（ms）。
_HEARTBEAT_INTERVAL_MS = 250
# 等待 Rust 先创建好段文件并完成初始化映射的最长时间。
_SEGMENT_WAIT_TIMEOUT = 15.0


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


class ShmServer:
    """基于 mmap 的共享内存服务循环。"""

    def __init__(self, path: str, max_workers: int = 8) -> None:
        self.path = path
        self._running = threading.Event()
        self._mm: mmap.mmap | None = None
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="shm-worker"
        )

    # ------------------------------------------------------------------
    # 生命周期
    # ------------------------------------------------------------------
    def serve_forever(self) -> None:
        """打开段、初始化协议头字段并进入调度循环（阻塞）。"""
        self._open_segment()
        self._reset_slots_to_idle()
        lifecycle = _LifecycleNotifier()
        lifecycle.on_starting()
        # 就绪后先置心跳，再置 ready=1（Rust 的 is_healthy 依赖两者）。
        self._write_u64(shm.OFF_HEARTBEAT, self._now_ms())
        self._write_u64(shm.OFF_READY, 1)
        heartbeat = threading.Thread(target=self._heartbeat_loop, daemon=True, name="shm-heartbeat")
        heartbeat.start()
        lifecycle.on_ready()
        lifecycle.on_running()
        logger.info(
            "共享内存服务就绪 path=%s",
            self.path,
            extra={
                "event": "sidecar.shm.starting",
                "feature": "runtime",
                "shm_path": self.path,
            },
        )
        try:
            self._dispatch_loop()
        finally:
            self.stop()

    def stop(self) -> None:
        self._running.set()
        self._executor.shutdown(wait=False)
        if self._mm is not None:
            # 下线前清就绪位，Rust 侧健康检查立即失败，触发重启编排。
            self._write_u64(shm.OFF_READY, 0)
            self._mm.flush()
            self._mm.close()
            self._mm = None

    # ------------------------------------------------------------------
    # 打开与初始化
    # ------------------------------------------------------------------
    def _open_segment(self) -> None:
        deadline = time.monotonic() + _SEGMENT_WAIT_TIMEOUT
        last_error: str | None = None
        while time.monotonic() < deadline:
            try:
                fd = os.open(self.path, os.O_RDWR)
                size = os.fstat(fd).st_size
                if size < shm.SEGMENT_SIZE:
                    os.close(fd)
                    last_error = f"段文件过小: {size} < {shm.SEGMENT_SIZE}"
                    time.sleep(0.05)
                    continue
                mm = mmap.mmap(fd, size, access=mmap.ACCESS_WRITE)
                os.close(fd)
            except FileNotFoundError:
                last_error = "段文件尚未创建"
                time.sleep(0.05)
                continue
            except OSError as error:
                last_error = str(error)
                time.sleep(0.05)
                continue
            self._mm = mm
            self._verify_header()
            return
        raise RuntimeError(f"等待共享内存段超时 path={self.path} last_error={last_error}")

    def _verify_header(self) -> None:
        mm = self._require_mm()
        if mm[:8] != shm.MAGIC:
            raise RuntimeError("共享内存协议头 magic 不匹配")
        version = self._read_u32(shm.OFF_VERSION)
        if version != shm.VERSION:
            raise RuntimeError(f"共享内存协议版本不匹配: {version} != {shm.VERSION}")
        slot_count = self._read_u32(shm.OFF_SLOT_COUNT)
        if slot_count != shm.SLOT_COUNT:
            raise RuntimeError(f"槽位数量不匹配: {slot_count} != {shm.SLOT_COUNT}")

    def _reset_slots_to_idle(self) -> None:
        """Rust 重启检测依赖：Python 启动即把全部槽位置 IDLE。"""
        mm = self._require_mm()
        for index in range(shm.SLOT_COUNT):
            offset = shm.slot_offset(index) + shm.STATE
            mm[offset : offset + 4] = struct.pack("<I", shm.STATE_IDLE)

    # ------------------------------------------------------------------
    # 后台心跳
    # ------------------------------------------------------------------
    def _heartbeat_loop(self) -> None:
        while not self._running.is_set():
            time.sleep(_HEARTBEAT_INTERVAL_MS / 1000)
            self._write_u64(shm.OFF_HEARTBEAT, self._now_ms())

    @staticmethod
    def _now_ms() -> int:
        return int(time.time() * 1000)

    # ------------------------------------------------------------------
    # 调度主循环
    # ------------------------------------------------------------------
    def _dispatch_loop(self) -> None:
        while not self._running.is_set():
            self._scan_slots()
            time.sleep(0.001)

    def _scan_slots(self) -> None:
        mm = self._require_mm()
        for index in range(shm.SLOT_COUNT):
            base = shm.slot_offset(index)
            state = struct.unpack_from("<I", mm, base + shm.STATE)[0]
            if state != shm.STATE_REQ_READY:
                continue
            # 单调度线程认领：REQ_READY → PROCESSING。
            struct.pack_into("<I", mm, base + shm.STATE, shm.STATE_PROCESSING)
            req_len = struct.unpack_from("<I", mm, base + shm.REQ_LEN)[0]
            if req_len > shm.REQ_CAP:
                self._write_response(
                    index,
                    status=500,
                    body=b'{"code":"req_too_large"}',
                    trace_id="",
                )
                continue
            req_seq = struct.unpack_from("<Q", mm, base + shm.REQ_SEQ)[0]
            raw = mm[base + shm.REQ_BUF : base + shm.REQ_BUF + req_len]
            self._executor.submit(self._handle_slot, index, raw, req_seq)

    # ------------------------------------------------------------------
    # 请求处理
    # ------------------------------------------------------------------
    def _handle_slot(self, index: int, raw: bytes, req_seq: int) -> None:
        started = time.perf_counter()
        trace_id = ""
        try:
            envelope = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as error:
            logger.warning("请求 envelope 解析失败 slot=%s error=%s", index, error)
            self._write_response(index, status=400, body=b'{"code":"bad_request"}', trace_id="")
            return
        method = envelope.get("method")
        path = envelope.get("path", "")
        body = envelope.get("body")
        if isinstance(body, dict):
            trace_id = str(body.get("trace_id", ""))

        # 控制面指令：Rust 优雅关闭时发送，响应后退出服务循环。
        if method == "POST" and path == "/v1/system/shutdown":
            self._write_response(
                index,
                status=200,
                body=json.dumps({"ok": True}).encode("utf-8"),
                trace_id=trace_id,
            )
            logger.info(
                "收到关闭指令，退出共享内存服务",
                extra={"event": "sidecar.shm.shutdown", "feature": "runtime"},
            )
            self._running.set()
            return

        if method != "POST" or path not in ROUTES:
            self._write_response(
                index,
                status=404,
                body=json.dumps({"code": "not_found", "message": "route not found"}).encode(),
                trace_id=trace_id,
            )
            _log_request_completed(
                path=path, status=404, duration_ms=_duration_ms(started), trace_id=trace_id
            )
            return

        _, handler_name = ROUTES[path]
        handler = HANDLERS.get(handler_name)
        if handler is None:
            self._write_response(
                index,
                status=500,
                body=b'{"code":"handler_missing"}',
                trace_id=trace_id,
            )
            return

        obs = get_runtime_observability()
        req_op = obs.begin_request(path, handler_name, trace_id)
        ok: bool | None = None
        try:
            result = handler(body if isinstance(body, dict) else None, trace_id=trace_id)
            if inspect.iscoroutine(result):
                loop = _get_async_loop()
                result = asyncio.run_coroutine_threadsafe(result, loop).result()
        except Exception as error:
            duration_ms = _duration_ms(started)
            obs.record_error(path=path, message=str(error), trace_id=trace_id)
            obs.end_request(req_op, ok=False)
            logger.exception(
                "接口调用异常 path=%s duration_ms=%s",
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
            self._write_response(
                index,
                status=500,
                body=b'{"code":"handler_error","message":"handler failed"}',
                trace_id=trace_id,
            )
            return

        if isinstance(result, dict) and "ok" in result:
            ok = bool(result.get("ok"))
            if ok is False:
                message = str(result.get("message") or "handler returned ok=false")
                obs.record_error(path=path, message=message, trace_id=trace_id)
        obs.end_request(req_op, ok=ok)
        payload = json.dumps(result, ensure_ascii=False).encode("utf-8")
        self._write_response(index, status=200, body=payload, trace_id=trace_id)
        _log_request_completed(
            path=path,
            status=200,
            duration_ms=_duration_ms(started),
            trace_id=trace_id,
            handler=handler_name,
            ok=ok,
        )

    def _write_response(self, index: int, *, status: int, body: bytes, trace_id: str) -> None:
        mm = self._require_mm()
        base = shm.slot_offset(index)
        if len(body) > shm.RES_CAP:
            logger.error(
                "响应超出缓冲区容量 path_index=%s len=%s cap=%s",
                index,
                len(body),
                shm.RES_CAP,
                extra={"feature": "runtime", "trace_id": trace_id},
            )
            body = b'{"code":"res_too_large"}'
            status = 500
        struct.pack_into("<I", mm, base + shm.STATUS, status)
        struct.pack_into("<I", mm, base + shm.RES_LEN, len(body))
        res_seq = struct.unpack_from("<Q", mm, base + shm.REQ_SEQ)[0]
        struct.pack_into("<Q", mm, base + shm.RES_SEQ, res_seq)
        mm[base + shm.RES_BUF : base + shm.RES_BUF + len(body)] = body
        # 最后发布状态，Rust 以 Acquire 读取。
        struct.pack_into("<I", mm, base + shm.STATE, shm.STATE_RES_READY)

    # ------------------------------------------------------------------
    # 底层 mmap 读写
    # ------------------------------------------------------------------
    def _require_mm(self) -> mmap.mmap:
        if self._mm is None:
            raise RuntimeError("共享内存段尚未打开")
        return self._mm

    def _read_u32(self, offset: int) -> int:
        return struct.unpack_from("<I", self._require_mm(), offset)[0]

    def _write_u32(self, offset: int, value: int) -> None:
        struct.pack_into("<I", self._require_mm(), offset, value)

    def _write_u64(self, offset: int, value: int) -> None:
        struct.pack_into("<Q", self._require_mm(), offset, value)


class _LifecycleNotifier:
    """最小生命周期钩子 — 共享内存模式无进程模型事件上报，仅打日志。"""

    def on_starting(self) -> None:
        logger.info("共享内存服务启动", extra={"event": "sidecar.starting", "feature": "runtime"})

    def on_ready(self) -> None:
        logger.info("共享内存服务就绪", extra={"event": "sidecar.ready", "feature": "runtime"})

    def on_running(self) -> None:
        logger.info("共享内存服务运行中", extra={"event": "sidecar.running", "feature": "runtime"})


def serve_shm(path: str) -> None:
    """共享内存模式入口 — 阻塞运行直到被停止。"""
    server = ShmServer(path)
    try:
        server.serve_forever()
    except Exception:
        logger.exception(
            "共享内存服务异常",
            extra={"event": "sidecar.failed", "feature": "runtime"},
        )
        raise
