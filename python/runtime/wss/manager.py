"""WebSocket 连接管理 — 多账号并行 + auto_reply + 风控续期（Python 内完成）。"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from config.settings import AiSettings
from crawlers.xianyu.login.cookie_renew import renew_cookies
from crawlers.xianyu.risk import RiskControlError
from crawlers.xianyu.ws.client import XianyuWsClient
from runtime.wss.auto_reply import maybe_auto_reply

logger = logging.getLogger("dingda.runtime.wss")

EventCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


def _auto_cookie_renew_enabled() -> bool:
    return os.environ.get("DINGDA_DISABLE_AUTO_COOKIE_RENEW", "").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }


@dataclass
class ManagedConnection:
    account_id: str
    client: XianyuWsClient
    task: asyncio.Task[None]
    auto_reply: bool
    ai_settings: AiSettings | None
    events: deque[dict[str, Any]] = field(default_factory=deque)


class WssManager:
    """进程内 WSS 连接注册表 — Rust 经 HTTP 启停，事件经 poll 拉回。"""

    def __init__(self) -> None:
        self._connections: dict[str, ManagedConnection] = {}
        self._lock = asyncio.Lock()
        # Camoufox 并发不稳定：全局串行续期。
        self._renew_lock = asyncio.Lock()

    async def connect(
        self,
        account_id: str,
        cookies: list[dict[str, Any]],
        *,
        auto_reply: bool = False,
        ai_settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        account_id = account_id.strip()
        if not account_id:
            return {"ok": False, "message": "account_id 必填"}
        if not cookies:
            return {"ok": False, "message": "cookies 必填"}

        parsed_settings: AiSettings | None = None
        if ai_settings:
            parsed_settings = AiSettings.from_payload({**ai_settings, "ai_enabled": True})

        async with self._lock:
            await self._disconnect_unlocked(account_id)

            async def on_event(event: dict[str, Any]) -> None:
                conn = self._connections.get(account_id)
                if conn is None:
                    return
                conn.events.append(event)
                if len(conn.events) > 500:
                    conn.events.popleft()
                if conn.auto_reply and conn.ai_settings is not None:
                    asyncio.create_task(
                        maybe_auto_reply(
                            conn.client,
                            event=event,
                            ai_settings=conn.ai_settings,
                            emit=on_event,
                        ),
                        name=f"auto-reply-{account_id}",
                    )

            async def on_risk(error: RiskControlError) -> list[dict[str, Any]] | None:
                return await self._renew_after_risk(
                    account_id,
                    cookies_provider=lambda: self._connections.get(account_id),
                    punish_url=error.punish_url,
                    emit=on_event,
                )

            client = XianyuWsClient(
                account_id=account_id,
                cookies=cookies,
                on_event=on_event,
                on_risk_renew=on_risk,
                auto_reply=auto_reply,
            )
            task = asyncio.create_task(client.run(), name=f"wss-{account_id}")
            self._connections[account_id] = ManagedConnection(
                account_id=account_id,
                client=client,
                task=task,
                auto_reply=auto_reply,
                ai_settings=parsed_settings if auto_reply else None,
            )

        logger.info(
            "WSS 连接任务已启动 account=%s auto_reply=%s",
            account_id,
            auto_reply,
        )
        return {"ok": True, "account_id": account_id, "status": "starting"}

    async def disconnect(self, account_id: str) -> dict[str, Any]:
        async with self._lock:
            await self._disconnect_unlocked(account_id.strip())
        return {"ok": True, "account_id": account_id}

    async def send_message(
        self,
        account_id: str,
        *,
        cid: str,
        peer_id: str,
        text: str,
    ) -> dict[str, Any]:
        conn = self._connections.get(account_id.strip())
        if conn is None:
            return {"ok": False, "message": "连接不存在"}
        try:
            await conn.client.send_text(cid, peer_id, text)
        except Exception as error:  # noqa: BLE001
            return {"ok": False, "message": str(error)}
        return {"ok": True}

    async def status(self, account_id: str | None = None) -> dict[str, Any]:
        if account_id:
            conn = self._connections.get(account_id.strip())
            if conn is None:
                return {"ok": True, "connections": []}
            return {
                "ok": True,
                "connections": [
                    {
                        "account_id": conn.account_id,
                        "status": conn.client.state.status,
                        "detail": conn.client.state.detail,
                        "queued_events": len(conn.events),
                        "auto_reply": conn.auto_reply,
                    },
                ],
            }
        return {
            "ok": True,
            "connections": [
                {
                    "account_id": c.account_id,
                    "status": c.client.state.status,
                    "queued_events": len(c.events),
                    "auto_reply": c.auto_reply,
                }
                for c in self._connections.values()
            ],
        }

    async def fetch_history(self, account_id: str, cid: str) -> dict[str, Any]:
        conn = self._connections.get(account_id.strip())
        if conn is None:
            return {"ok": False, "message": "连接不存在", "messages": []}
        try:
            messages = await conn.client.fetch_history(cid)
        except Exception as error:  # noqa: BLE001
            return {"ok": False, "message": str(error), "messages": []}
        return {"ok": True, "messages": messages}

    async def poll_events(self, account_id: str, *, limit: int = 50) -> dict[str, Any]:
        conn = self._connections.get(account_id.strip())
        if conn is None:
            return {"ok": True, "events": []}
        limit = max(1, min(limit, 200))
        events: list[dict[str, Any]] = []
        while conn.events and len(events) < limit:
            events.append(conn.events.popleft())
        return {"ok": True, "events": events}

    def snapshot_sync(self) -> dict[str, Any]:
        """同步快照 — 供 runtime observability 轮询（同进程，不经 async）。"""
        return {
            "connections": [
                {
                    "account_id": conn.account_id,
                    "status": conn.client.state.status,
                    "detail": conn.client.state.detail,
                    "queued_events": len(conn.events),
                    "auto_reply": conn.auto_reply,
                }
                for conn in self._connections.values()
            ],
        }

    async def _renew_after_risk(
        self,
        account_id: str,
        *,
        cookies_provider: Callable[[], ManagedConnection | None],
        punish_url: str | None,
        emit: EventCallback,
    ) -> list[dict[str, Any]] | None:
        if not _auto_cookie_renew_enabled():
            await emit(
                {
                    "type": "status",
                    "account_id": account_id,
                    "state": "error",
                    "detail": "风控拦截，自动过滑块未启用",
                },
            )
            return None

        await emit(
            {
                "type": "status",
                "account_id": account_id,
                "state": "queued" if self._renew_lock.locked() else "renewing",
                "detail": "排队等待过滑块，请稍候"
                if self._renew_lock.locked()
                else "正在过滑块验证，请稍候",
            },
        )

        async with self._renew_lock:
            conn = cookies_provider()
            if conn is None:
                return None
            await emit(
                {
                    "type": "status",
                    "account_id": account_id,
                    "state": "renewing",
                    "detail": "正在打开浏览器完成滑块验证",
                },
            )
            ok, detail, data = await renew_cookies(
                list(conn.client.cookies),
                account_id=account_id,
                punish_url=punish_url,
            )
            if not ok:
                await emit(
                    {
                        "type": "status",
                        "account_id": account_id,
                        "state": "error",
                        "detail": f"滑块续期失败：{(detail or '')[:80]}",
                    },
                )
                return None
            renewed = data.get("cookies")
            if not isinstance(renewed, list) or not renewed:
                await emit(
                    {
                        "type": "status",
                        "account_id": account_id,
                        "state": "error",
                        "detail": "续期未返回 Cookie",
                    },
                )
                return None
            await emit(
                {
                    "type": "cookies_updated",
                    "account_id": account_id,
                    "cookies": renewed,
                },
            )
            await emit(
                {
                    "type": "status",
                    "account_id": account_id,
                    "state": "connecting",
                    "detail": "滑块通过，正在重连",
                },
            )
            logger.info("风控续期成功，将重试 WSS account=%s", account_id)
            return renewed

    async def _disconnect_unlocked(self, account_id: str) -> None:
        conn = self._connections.pop(account_id, None)
        if conn is None:
            return
        conn.client.request_stop()
        conn.task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await conn.task


_manager: WssManager | None = None


def get_wss_manager() -> WssManager:
    global _manager
    if _manager is None:
        _manager = WssManager()
    return _manager
