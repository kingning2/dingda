"""扫码登录会话管理（薄编排层 → channels.registry）。"""

from __future__ import annotations

import time
import uuid
from threading import Lock
from typing import Any

from channels.base import QrLoginChannel
from channels.registry import create_qr_login_channel
from channels.types import LoginStatus
from contracts.channel import (
    QrCancelResponse,
    QrCheckResponse,
    QrStartRequest,
    QrStartResponse,
)
from core.logging import info
from domains.account.persist import save_login_credentials
from core.errors import AppError

SESSION_TTL_SECONDS = 300
_PLATFORM_TIMEOUT: dict[str, int] = {
    "xianyu": 120,
    "xiaohongshu": 240,
    "ali1688": 180,
}


class QrSession:
    def __init__(
        self,
        session_id: str,
        platform: str,
        created_at: float,
        channel: QrLoginChannel,
        runtime: Any,
    ) -> None:
        self.session_id = session_id
        self.platform = platform
        self.created_at = created_at
        self.channel = channel
        self.runtime = runtime


class ChannelQrService:
    def __init__(self) -> None:
        self._sessions: dict[str, QrSession] = {}
        self._lock = Lock()

    def start(self, request: QrStartRequest) -> QrStartResponse:
        self._purge_expired()
        info("channel.qr.start", {"platform": request.platform})
        channel = create_qr_login_channel(request.platform)
        timeout = _PLATFORM_TIMEOUT.get(request.platform, 120)
        # 关掉弹窗再开会再 start：必须先取消旧任务，否则会堵在同步浏览器线程上
        self._abandon_inflight(request.platform)
        # HTTP /qr/start 等到 runtime.ready：浏览器起来 + 第一张二维码
        started = time.monotonic()
        runtime = channel.start_login(timeout=timeout)

        session_id = f"qr-{uuid.uuid4().hex}"
        session = QrSession(
            session_id=session_id,
            platform=request.platform,
            created_at=time.monotonic(),
            channel=channel,
            runtime=runtime,
        )
        with self._lock:
            self._sessions[session_id] = session

        if not runtime.ready.wait(timeout=25):
            elapsed_ms = int((time.monotonic() - started) * 1000)
            self._drop(session_id)
            info(
                "channel.qr.start_timeout",
                {
                    "platform": request.platform,
                    "elapsed_ms": elapsed_ms,
                },
            )
            raise AppError(
                "channel.qr_start_timeout",
                "生成二维码超时，请确认已安装 Camoufox 并重试",
                status_code=504,
            )

        elapsed_ms = int((time.monotonic() - started) * 1000)
        snapshot = self._snapshot(session)
        if snapshot["status"] == LoginStatus.FAILED.value:
            detail = snapshot.get("detail") or "无法启动扫码登录"
            self._drop(session_id)
            info(
                "channel.qr.start_failed",
                {
                    "platform": request.platform,
                    "detail": detail,
                    "elapsed_ms": elapsed_ms,
                },
            )
            raise AppError("channel.qr_start_failed", detail, status_code=503)

        info(
            "channel.qr.start_ok",
            {
                "platform": request.platform,
                "session_id": session_id,
                "status": snapshot["status"],
                "elapsed_ms": elapsed_ms,
            },
        )
        return QrStartResponse(
            ok=True,
            status=snapshot["status"],
            session_id=session_id,
            qr_base64=snapshot.get("qr_base64"),
            qr_url=snapshot.get("qr_url"),
            detail=snapshot.get("detail"),
        )

    def check(self, session_id: str) -> QrCheckResponse:
        self._purge_expired()
        session = self._get(session_id)
        snapshot = self._snapshot(session)
        info(
            "channel.qr.check",
            {
                "session_id": session_id,
                "platform": session.platform,
                "status": snapshot["status"],
            },
        )
        terminal = snapshot["status"] in {
            LoginStatus.SUCCESS.value,
            LoginStatus.FAILED.value,
            LoginStatus.EXPIRED.value,
        }
        if snapshot["status"] == LoginStatus.SUCCESS.value:
            save_login_credentials(
                platform=session.platform,
                account_id=snapshot.get("account_id"),
                display_name=snapshot.get("display_name"),
                avatar_url=snapshot.get("avatar_url"),
                cookie=snapshot.get("cookie"),
                local_storage=snapshot.get("local_storage")
                if isinstance(snapshot.get("local_storage"), dict)
                else None,
            )
            info(
                "channel.qr.success",
                {
                    "session_id": session_id,
                    "account_id": snapshot.get("account_id"),
                    "platform": session.platform,
                    "display_name": snapshot.get("display_name"),
                    "has_avatar": bool(snapshot.get("avatar_url")),
                },
            )
        if terminal:
            self._drop(session_id)
        return QrCheckResponse(
            ok=snapshot["status"] != LoginStatus.FAILED.value,
            status=snapshot["status"],
            session_id=session_id,
            qr_base64=snapshot.get("qr_base64"),
            qr_url=snapshot.get("qr_url"),
            detail=snapshot.get("detail"),
            account_id=snapshot.get("account_id"),
            display_name=snapshot.get("display_name"),
            avatar_url=snapshot.get("avatar_url"),
            cookie=snapshot.get("cookie"),
        )

    def cancel(self, session_id: str) -> QrCancelResponse:
        """前端关弹窗：置 cancel 并丢掉会话，后台扫码立刻让出浏览器。"""
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is None:
            info("channel.qr.cancel_miss", {"session_id": session_id})
            return QrCancelResponse(
                ok=True,
                session_id=session_id,
                detail="会话不存在或已结束",
            )
        cancel = getattr(session.runtime, "cancel", None)
        if cancel is not None:
            cancel.set()
        info(
            "channel.qr.cancelled",
            {"session_id": session_id, "platform": session.platform},
        )
        return QrCancelResponse(
            ok=True,
            session_id=session_id,
            detail="已取消扫码",
        )

    def _snapshot(self, session: QrSession) -> dict[str, object]:
        return session.channel.snapshot(session.runtime).as_dict()

    def _get(self, session_id: str) -> QrSession:
        with self._lock:
            session = self._sessions.get(session_id)
        if not session:
            raise AppError("channel.qr_not_found", "扫码会话不存在或已过期", status_code=404)
        return session

    def _drop(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def _abandon_inflight(self, platform: str) -> None:
        """取消同平台未结束的扫码，让出 Camoufox 专用线程。"""
        with self._lock:
            dropping = [
                session
                for session in self._sessions.values()
                if session.platform == platform
            ]
            for session in dropping:
                self._sessions.pop(session.session_id, None)
        for session in dropping:
            cancel = getattr(session.runtime, "cancel", None)
            if cancel is not None:
                cancel.set()
            info(
                "channel.qr.abandoned",
                {"session_id": session.session_id, "platform": platform},
            )

    def _purge_expired(self) -> None:
        now = time.monotonic()
        with self._lock:
            expired = [
                session_id
                for session_id, session in self._sessions.items()
                if now - session.created_at > SESSION_TTL_SECONDS
            ]
            for session_id in expired:
                self._sessions.pop(session_id, None)


_service = ChannelQrService()


def get_channel_qr_service() -> ChannelQrService:
    return _service
