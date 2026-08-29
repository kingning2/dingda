"""共享内存服务端 — 槽位协议与请求处理。

由 hybrid 入口调用 ``bootstrap`` / ``wake_slot`` / ``scan_slots``。
请求 envelope::

    {"method": "POST"|"GET", "path": "/v1/...", "body": {...}}

业务分发复用 ``runtime.dispatch.dispatch_post``。
"""

from __future__ import annotations

import json
import logging
import mmap
import os
import struct
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from dingda_sidecar.runtime import shm_protocol as shm
from dingda_sidecar.runtime.dispatch import dispatch_post
from dingda_sidecar.runtime.handlers.runtime import build_runtime_status

logger = logging.getLogger("dingda.runtime.shm")

_HEARTBEAT_INTERVAL_MS = 250
_SEGMENT_WAIT_TIMEOUT = 15.0


class ShmServer:
    """基于 mmap 的共享内存服务。"""

    def __init__(self, path: str, max_workers: int = 8) -> None:
        self.path = path
        self._stopped = threading.Event()
        self._mm: mmap.mmap | None = None
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="shm-worker"
        )
        self._slot_lock = threading.Lock()

    def bootstrap(self) -> None:
        """打开段、重置槽位、置 ready 并启动心跳（不进入忙轮询）。"""
        self._open_segment()
        self._reset_slots_to_idle()
        self._write_u64(shm.OFF_HEARTBEAT, self._now_ms())
        self._write_u64(shm.OFF_READY, 1)
        heartbeat = threading.Thread(target=self._heartbeat_loop, daemon=True, name="shm-heartbeat")
        heartbeat.start()
        logger.info(
            "共享内存服务就绪 path=%s",
            self.path,
            extra={
                "event": "sidecar.shm.ready",
                "feature": "runtime",
                "shm_path": self.path,
            },
        )

    def is_stopped(self) -> bool:
        return self._stopped.is_set()

    def stop(self) -> None:
        if self._stopped.is_set():
            return
        self._stopped.set()
        self._executor.shutdown(wait=False)
        if self._mm is not None:
            self._write_u64(shm.OFF_READY, 0)
            self._mm.flush()
            self._mm.close()
            self._mm = None

    def wake_slot(self, index: int) -> None:
        """处理单个槽位（由 pipe ``shm.wake`` 触发）。"""
        if index < 0 or index >= shm.SLOT_COUNT:
            self.scan_slots()
            return
        self._claim_and_dispatch(index)

    def scan_slots(self) -> None:
        """扫描全部 ``REQ_READY`` 槽位。"""
        for index in range(shm.SLOT_COUNT):
            self._claim_and_dispatch(index)

    def _claim_and_dispatch(self, index: int) -> None:
        with self._slot_lock:
            mm = self._require_mm()
            base = shm.slot_offset(index)
            state = struct.unpack_from("<I", mm, base + shm.STATE)[0]
            if state != shm.STATE_REQ_READY:
                return
            struct.pack_into("<I", mm, base + shm.STATE, shm.STATE_PROCESSING)
            req_len = struct.unpack_from("<I", mm, base + shm.REQ_LEN)[0]
            if req_len > shm.REQ_CAP:
                self._write_response(
                    index,
                    status=500,
                    body=b'{"code":"req_too_large"}',
                    trace_id="",
                )
                return
            req_seq = struct.unpack_from("<Q", mm, base + shm.REQ_SEQ)[0]
            raw = bytes(mm[base + shm.REQ_BUF : base + shm.REQ_BUF + req_len])
        self._executor.submit(self._handle_slot, index, raw, req_seq)

    def serve_forever(self) -> None:
        """兼容旧入口：bootstrap + 低频扫描直到 stop。"""
        self.bootstrap()
        try:
            while not self._stopped.is_set():
                self.scan_slots()
                time.sleep(0.2)
        finally:
            self.stop()

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
        mm = self._require_mm()
        for index in range(shm.SLOT_COUNT):
            offset = shm.slot_offset(index) + shm.STATE
            mm[offset : offset + 4] = struct.pack("<I", shm.STATE_IDLE)

    def _heartbeat_loop(self) -> None:
        while not self._stopped.is_set():
            time.sleep(_HEARTBEAT_INTERVAL_MS / 1000)
            if self._mm is None:
                break
            self._write_u64(shm.OFF_HEARTBEAT, self._now_ms())

    @staticmethod
    def _now_ms() -> int:
        return int(time.time() * 1000)

    def _handle_slot(self, index: int, raw: bytes, _req_seq: int) -> None:
        try:
            envelope = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as error:
            logger.warning("请求 envelope 解析失败 slot=%s error=%s", index, error)
            self._write_response(index, status=400, body=b'{"code":"bad_request"}', trace_id="")
            return

        method = str(envelope.get("method") or "POST").upper()
        path = str(envelope.get("path") or "")
        body = envelope.get("body")
        trace_id = ""
        if isinstance(body, dict):
            trace_id = str(body.get("trace_id", ""))

        if method == "GET":
            if path == "/health":
                self._write_response(
                    index,
                    status=200,
                    body=b'{"status":"ok"}',
                    trace_id=trace_id,
                )
                return
            if path == "/v1/runtime/status":
                encoded = json.dumps(build_runtime_status(), ensure_ascii=False).encode("utf-8")
                self._write_response(index, status=200, body=encoded, trace_id=trace_id)
                return
            self._write_response(
                index,
                status=404,
                body=b'{"code":"not_found","message":"route not found"}',
                trace_id=trace_id,
            )
            return

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
            self.stop()
            return

        payload = body if isinstance(body, dict) else None
        result = dispatch_post(path, payload, method=method)
        encoded = json.dumps(result.body, ensure_ascii=False).encode("utf-8")
        self._write_response(index, status=result.status, body=encoded, trace_id=trace_id)

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
        struct.pack_into("<I", mm, base + shm.STATE, shm.STATE_RES_READY)

    def _require_mm(self) -> mmap.mmap:
        if self._mm is None:
            raise RuntimeError("共享内存段尚未打开")
        return self._mm

    def _read_u32(self, offset: int) -> int:
        return struct.unpack_from("<I", self._require_mm(), offset)[0]

    def _write_u64(self, offset: int, value: int) -> None:
        struct.pack_into("<Q", self._require_mm(), offset, value)


def serve_shm(path: str) -> None:
    """仅 SHM 模式（无管道唤醒）— 低频扫描兜底。"""
    server = ShmServer(path)
    try:
        server.serve_forever()
    except Exception:
        logger.exception(
            "共享内存服务异常",
            extra={"event": "sidecar.failed", "feature": "runtime"},
        )
        raise
