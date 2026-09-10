"""DOM 修复的校验桥：宿主进程起临时 HTTP 监听，供子 agent 回打。

职责：
    持有修复现场那一页（page + adapter + item_id）。修复子 agent 的选择器校验工具
    POST 过来，就在**同一个页面**上跑平台抽取脚本，把 payload 或失败原样回去。

设计说明：
    - live page 只存在于宿主进程（FastAPI 或 MCP stdio 子进程）；子 agent 的 MCP 是
      另一个兄弟进程，内存不共享 —— 所以走 localhost HTTP（对齐 ``tools/live_push`` 的思路）
    - 绑 ``127.0.0.1`` 的临时端口，只活在一次 repair 期间
    - 页面是 async（Playwright），HTTP handler 在别的线程 → ``run_coroutine_threadsafe``

使用示例：
    bridge = ValidationBridge(page, adapter, item_id="123")
    url = bridge.start()
    try:
        ...  # url 交给子 agent
    finally:
        bridge.stop()
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from src.browser.port import Page
from src.crawler.extraction.repair.types import PlatformRepairAdapter

logger = logging.getLogger("dingda.crawler.repair.bridge")

_MAX_BODY_BYTES = 64 * 1024
_EVALUATE_TIMEOUT_S = 60.0


class ValidationBridge:
    """一次 repair 期间的校验监听。"""

    def __init__(
        self,
        page: Page,
        adapter: PlatformRepairAdapter,
        *,
        item_id: str,
    ) -> None:
        self._page = page
        self._adapter = adapter
        self._item_id = str(item_id)
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server: ThreadingHTTPServer | None = None

    @property
    def url(self) -> str:
        """校验工具回打的地址；未启动时为空串。"""
        if self._server is None:
            return ""
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}/validate"

    def start(self) -> str:
        """起监听并返回 url；必须在持有 page 的事件循环里调用。"""
        self._loop = asyncio.get_running_loop()
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _make_handler(self))
        threading.Thread(
            target=self._server.serve_forever,
            name="dom-repair-bridge",
            daemon=True,
        ).start()
        logger.info("repair bridge listen url=%s item_id=%s", self.url, self._item_id)
        return self.url

    def stop(self) -> None:
        """关监听。幂等。"""
        server, self._server = self._server, None
        if server is None:
            return
        server.shutdown()
        server.server_close()
        logger.info("repair bridge closed item_id=%s", self._item_id)

    def validate(self, selectors: dict[str, Any]) -> dict[str, Any]:
        """在修复现场那一页上跑候选选择器（阻塞，供 HTTP handler 调）。"""
        loop = self._loop
        if loop is None:
            return {"error": "bridge-not-started"}
        future = asyncio.run_coroutine_threadsafe(
            self._adapter.evaluate_extract(self._page, selectors, item_id=self._item_id),
            loop,
        )
        try:
            payload = future.result(timeout=_EVALUATE_TIMEOUT_S)
        except Exception as exc:  # noqa: BLE001
            logger.warning("repair bridge evaluate failed: %s", exc)
            return {"error": "bridge-evaluate-failed", "message": str(exc)}
        return payload if isinstance(payload, dict) else {"error": "bridge-bad-payload"}


def _make_handler(bridge: ValidationBridge) -> type[BaseHTTPRequestHandler]:
    """构造只认 ``POST /validate`` 的最小 handler。"""

    class _ValidateHandler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler 约定
            if self.path.rstrip("/") != "/validate":
                self._reply(404, {"error": "not-found"})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = 0
            if length <= 0 or length > _MAX_BODY_BYTES:
                self._reply(400, {"error": "bad-body"})
                return
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                self._reply(400, {"error": "bad-json"})
                return
            selectors = body.get("selectors") if isinstance(body, dict) else None
            if not isinstance(selectors, dict) or not selectors:
                self._reply(400, {"error": "selectors-required"})
                return
            logger.info(
                "repair bridge validate keys=%s item_id=%s",
                sorted(selectors.keys())[:12],
                bridge._item_id,
            )
            self._reply(200, bridge.validate(selectors))

        def _reply(self, status: int, payload: dict[str, Any]) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, fmt: str, *args: Any) -> None:
            logger.debug("repair bridge http %s", fmt % args)

    return _ValidateHandler
