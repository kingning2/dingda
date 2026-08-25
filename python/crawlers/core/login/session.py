"""扫码登录会话与状态常量。"""

from __future__ import annotations

import asyncio
import contextlib
import time
from typing import Any

# 扫码状态机
STATUS_GENERATING = "generating"
STATUS_READY = "ready"
STATUS_WAITING = "waiting"
STATUS_SCANNED = "scanned"
STATUS_CONFIRMED = "confirmed"
STATUS_SUCCESS = "success"
STATUS_REFRESHED = "refreshed"
STATUS_EXPIRED = "expired"
STATUS_FAILED = "failed"

QR_WAIT_TIMEOUT_MS = 15000
QR_REFRESH_SECONDS = 30
QR_EXPIRE_SECONDS = 300


class QrSession:
    """一次扫码登录的 Playwright 会话。"""

    def __init__(self, session_id: str, platform: str) -> None:
        self.session_id = session_id
        self.platform = platform
        self.browser: Any | None = None
        self.context: Any | None = None
        self.page: Any | None = None
        self.status = STATUS_GENERATING
        self.started_at = time.monotonic()
        self.last_refresh_at = time.monotonic()
        self.qr_base64: str | None = None
        self.qr_code_content: str | None = None
        self.last_emitted_qr_content: str | None = None
        self.qr_progress: str | None = None
        self.detail = ""
        self.lock = asyncio.Lock()

    async def close(self) -> None:
        with contextlib.suppress(Exception):
            if self.context:
                await self.context.close()
        with contextlib.suppress(Exception):
            if self.browser:
                await self.browser.close()
        self.browser = None
        self.context = None
        self.page = None


# 全局进行中的扫码会话（跨 HTTP 请求共享）。
QR_SESSIONS: dict[str, QrSession] = {}
