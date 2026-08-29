"""闲鱼 WebSocket 长连接客户端。

负责注册、心跳、收发 LWP 帧，并将 syncPush 解析为入站消息回调给 WSS 管理器。"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection

from dingda_sidecar.crawlers.goofish.risk import RiskControlError
from dingda_sidecar.crawlers.goofish.ws import frames
from dingda_sidecar.crawlers.goofish.ws.constants import (
    HEARTBEAT_INTERVAL_SEC,
    HISTORY_FIRST_CURSOR,
    HISTORY_MAX_PAGES,
    HISTORY_PAGE_LIMIT,
    HISTORY_RESPONSE_TIMEOUT_SEC,
    LOGIN_REFRESH_INTERVAL_SEC,
    RECONNECT_BACKOFF_INITIAL_SEC,
    RECONNECT_BACKOFF_MAX_SEC,
    RECONNECT_NORMAL_EXIT_DELAY_SEC,
    USER_AGENT,
    VULCAN_WAIT_SEC,
    WEB_ORIGIN,
    WS_URL,
)
from dingda_sidecar.crawlers.goofish.ws.cookies import (
    clean_cookie_header,
    cookies_to_header,
    device_id_from_cookie,
    my_id,
    now_ms,
    parse_cookies,
)
from dingda_sidecar.crawlers.goofish.ws.history import parse_history_message
from dingda_sidecar.crawlers.goofish.ws.push import PushBatch, parse_sync_push_package
from dingda_sidecar.crawlers.goofish.ws.token import TokenError, fetch_ws_token, refresh_login

logger = logging.getLogger("dingda.crawlers.goofish.ws.client")

EventCallback = Callable[[dict[str, Any]], Awaitable[None] | None]
RiskRenewCallback = Callable[[RiskControlError], Awaitable[list[dict[str, Any]] | None]]


@dataclass
class WsConnectionState:
    account_id: str
    status: str = "disconnected"
    detail: str = ""
    connected_at: float | None = None


@dataclass
class XianyuWsClient:
    account_id: str
    cookies: list[dict[str, Any]]
    on_event: EventCallback | None = None
    on_risk_renew: RiskRenewCallback | None = None
    auto_reply: bool = False

    _stop: asyncio.Event = field(default_factory=asyncio.Event, init=False)
    _outbound: asyncio.Queue[str] = field(default_factory=asyncio.Queue, init=False)
    _pending: dict[str, asyncio.Future[dict[str, Any]]] = field(default_factory=dict, init=False)
    _vulcan_ready: bool = field(default=False, init=False)
    state: WsConnectionState = field(init=False)

    def __post_init__(self) -> None:
        self.state = WsConnectionState(account_id=self.account_id)

    def request_stop(self) -> None:
        self._stop.set()

    async def send_text(self, cid: str, peer_id: str, text: str) -> None:
        header = cookies_to_header(self.cookies)
        unb = my_id(parse_cookies(header))
        if not unb:
            raise ValueError("cookie 缺少 unb")
        frame = frames.send_message_frame(cid, peer_id, unb, text)
        await self._outbound.put(json.dumps(frame, ensure_ascii=False))

    async def fetch_history(
        self,
        cid: str,
        *,
        limit: int = HISTORY_PAGE_LIMIT,
    ) -> list[dict[str, Any]]:
        if self.state.status != "connected":
            raise RuntimeError("WS 未连接")
        all_messages: list[dict[str, Any]] = []
        cursor = HISTORY_FIRST_CURSOR
        for _ in range(HISTORY_MAX_PAGES):
            frame = frames.list_user_messages_frame(cid, cursor, limit)
            mid = str((frame.get("headers") or {}).get("mid") or "")
            if not mid:
                raise RuntimeError("历史请求缺少 mid")
            loop = asyncio.get_running_loop()
            future: asyncio.Future[dict[str, Any]] = loop.create_future()
            self._pending[mid] = future
            await self._outbound.put(json.dumps(frame, ensure_ascii=False))
            try:
                body = await asyncio.wait_for(future, timeout=HISTORY_RESPONSE_TIMEOUT_SEC)
            except TimeoutError as error:
                self._pending.pop(mid, None)
                raise TimeoutError("拉取消息历史超时") from error
            code = body.get("code")
            if isinstance(code, int) and code != 200:
                raise RuntimeError(f"listUserMessages 返回 code={code}")
            models = body.get("userMessageModels")
            if isinstance(models, list):
                for model in models:
                    if isinstance(model, dict):
                        parsed = parse_history_message(model)
                        if parsed is not None:
                            all_messages.append(parsed)
            has_more = body.get("hasMore") == 1
            if not has_more:
                break
            next_cursor = body.get("nextCursor")
            if isinstance(next_cursor, int) and next_cursor > 0:
                cursor = next_cursor
            else:
                break
        return all_messages

    async def run(self) -> None:
        keepalive = asyncio.create_task(self._keepalive_loop())
        backoff = RECONNECT_BACKOFF_INITIAL_SEC
        try:
            while not self._stop.is_set():
                try:
                    await self._run_once()
                    logger.info(
                        "WS 正常退出，%ss 后重连 account=%s",
                        RECONNECT_NORMAL_EXIT_DELAY_SEC,
                        self.account_id,
                    )
                    backoff = RECONNECT_BACKOFF_INITIAL_SEC
                    await asyncio.sleep(RECONNECT_NORMAL_EXIT_DELAY_SEC)
                except TokenError as error:
                    await self._emit(
                        {
                            "type": "auth_expired",
                            "account_id": self.account_id,
                            "detail": str(error),
                        },
                    )
                    self.state.status = "auth_expired"
                    break
                except RiskControlError as error:
                    logger.warning(
                        "WS 风控拦截 account=%s detail=%s",
                        self.account_id,
                        error.detail,
                    )
                    self.state.status = "risk"
                    renewed: list[dict[str, Any]] | None = None
                    if self.on_risk_renew is not None:
                        try:
                            renewed = await self.on_risk_renew(error)
                        except Exception:  # noqa: BLE001
                            logger.exception("风控续期回调失败 account=%s", self.account_id)
                    if renewed:
                        self.cookies = renewed
                        self.state.status = "connecting"
                        backoff = RECONNECT_BACKOFF_INITIAL_SEC
                        continue
                    await self._emit(
                        {
                            "type": "error",
                            "account_id": self.account_id,
                            "detail": error.detail,
                        },
                    )
                    break
                except websockets.exceptions.ConnectionClosed as error:
                    logger.warning(
                        "WS 断连 account=%s detail=%s backoff=%.1fs",
                        self.account_id,
                        error,
                        backoff,
                    )
                    self.state.status = "connecting"
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, RECONNECT_BACKOFF_MAX_SEC)
                except asyncio.CancelledError:
                    raise
                except Exception as error:  # noqa: BLE001
                    logger.exception("WS 会话异常 account=%s detail=%s", self.account_id, error)
                    await self._emit(
                        {
                            "type": "error",
                            "account_id": self.account_id,
                            "detail": str(error),
                        },
                    )
                    self.state.status = "error"
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, RECONNECT_BACKOFF_MAX_SEC)
                if self._stop.is_set():
                    break
        finally:
            keepalive.cancel()
            with suppress(asyncio.CancelledError):
                await keepalive
            self.state.status = "disconnected"
            await self._emit({"type": "disconnected", "account_id": self.account_id})

    async def _keepalive_loop(self) -> None:
        while not self._stop.is_set():
            await asyncio.sleep(LOGIN_REFRESH_INTERVAL_SEC)
            if self._stop.is_set():
                break
            try:
                _, updated = await asyncio.to_thread(refresh_login, self.cookies)
                self.cookies = updated
                logger.debug("login refreshed account=%s", self.account_id)
            except Exception as error:  # noqa: BLE001
                logger.warning("login refresh failed account=%s detail=%s", self.account_id, error)

    async def _run_once(self) -> None:
        header = clean_cookie_header(cookies_to_header(self.cookies))
        parsed = parse_cookies(header)
        unb = my_id(parsed)
        device_id = device_id_from_cookie(header)
        if not unb or not device_id:
            raise TokenError("cookie 无效，缺少 unb")

        self.state.status = "connecting"
        self._vulcan_ready = False
        await self._emit({"type": "connecting", "account_id": self.account_id})

        token = await asyncio.to_thread(fetch_ws_token, self.cookies)
        logger.info("WS token 获取成功 account=%s", self.account_id)

        async with websockets.connect(
            WS_URL,
            additional_headers={
                "Cookie": header,
                "Host": "wss-goofish.dingtalk.com",
                "Connection": "Upgrade",
                "Pragma": "no-cache",
                "Cache-Control": "no-cache",
                "Origin": WEB_ORIGIN,
                "User-Agent": USER_AGENT,
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
            open_timeout=30,
            ping_interval=None,
            max_size=4 * 1024 * 1024,
        ) as ws:
            self.state.status = "connected"
            self.state.connected_at = asyncio.get_event_loop().time()
            await self._emit({"type": "connected", "account_id": self.account_id})

            await ws.send(json.dumps(frames.register_frame(device_id, token)))
            await ws.send(json.dumps(frames.sync_ack_frame(pts=now_ms() * 1000)))

            vulcan_deadline = asyncio.get_event_loop().time() + VULCAN_WAIT_SEC
            heartbeat = asyncio.create_task(self._heartbeat_loop(ws))
            try:
                while not self._stop.is_set():
                    now = asyncio.get_event_loop().time()
                    if not self._vulcan_ready and now >= vulcan_deadline:
                        self._vulcan_ready = True

                    incoming = await self._recv_or_send(ws)
                    if incoming is None:
                        break
                    if incoming == "__sent__":
                        continue

                    msg = incoming
                    headers = msg.get("headers") or {}
                    if isinstance(headers, dict) and headers:
                        mid = str(headers.get("mid") or "")
                        pending = self._pending.pop(mid, None) if mid else None
                        if pending is not None and not pending.done():
                            body = msg.get("body")
                            if isinstance(body, dict):
                                pending.set_result(body)
                            else:
                                pending.set_result(msg if isinstance(msg, dict) else {})
                            continue
                        await ws.send(json.dumps(frames.ack_frame(headers)))

                    if msg.get("lwp") == "/s/vulcan":
                        self._vulcan_ready = True

                    batch = parse_sync_push_package(msg)
                    await self._handle_push(batch)
            finally:
                heartbeat.cancel()
                with suppress(asyncio.CancelledError):
                    await heartbeat

    async def _heartbeat_loop(self, ws: ClientConnection) -> None:
        while True:
            try:
                await ws.send(json.dumps(frames.heartbeat_frame()))
            except Exception as error:  # noqa: BLE001
                logger.debug("heartbeat send failed account=%s detail=%s", self.account_id, error)
                return
            await asyncio.sleep(HEARTBEAT_INTERVAL_SEC)

    async def _recv_or_send(self, ws: ClientConnection) -> dict[str, Any] | str | None:
        send_task = asyncio.create_task(self._outbound.get())
        recv_task = asyncio.create_task(ws.recv())
        done, pending = await asyncio.wait(
            {send_task, recv_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        if send_task in done:
            frame = send_task.result()
            await ws.send(frame)
            return "__sent__"
        raw = recv_task.result()
        if not isinstance(raw, str):
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    async def _handle_push(self, batch: PushBatch) -> None:
        for session in batch.sessions:
            await self._emit(
                {
                    "type": "session",
                    "account_id": self.account_id,
                    "cid": session.cid,
                    "item_id": session.item_id,
                    "item_title": session.item_title,
                    "updated_at": session.updated_at,
                },
            )
        for message in batch.messages:
            await self._emit(
                {
                    "type": "message",
                    "account_id": self.account_id,
                    "cid": message.cid,
                    "peer_id": message.peer_id,
                    "peer_name": message.peer_name,
                    "item_id": message.item_id,
                    "content": message.content,
                    "created_at_ms": message.created_at_ms,
                },
            )

    async def _emit(self, event: dict[str, Any]) -> None:
        if self.on_event is None:
            return
        result = self.on_event(event)
        if asyncio.iscoroutine(result):
            await result
