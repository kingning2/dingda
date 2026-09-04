"""闲鱼 IM WebSocket 运行时（LWP over wss-goofish.dingtalk.com）。

职责：
    连接、/reg、心跳、ack、发消息、拉历史、短时收集会话 cid；
    依赖本包 Session / sign / token。

设计说明：
    - 平台：闲鱼（xianyu）
    - 调用方：channels/xianyu/message；不直接供 Tool 或 Agent
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from typing import Any

import websockets
from websockets.asyncio.client import ClientConnection

from src.channels.xianyu.session import Session
from src.channels.xianyu.sign import decrypt, generate_mid, generate_uuid
from src.channels.xianyu.token import IM_APP_KEY, get_access_token, refresh_login

logger = logging.getLogger("dingda.channel.xianyu.ws")

WS_URL = "wss://wss-goofish.dingtalk.com/"
UA_WEB = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
)
UA_IM = (
    UA_WEB
    + " DingTalk(2.1.5) OS(Windows/10) Browser(Chrome/133.0.0.0) "
    + "DingWeb/2.1.5 IMPaaS DingWeb/2.1.5"
)


def _cookie_header(session: Session) -> str:
    return "; ".join(f"{k}={v}" for k, v in session.http.cookies.get_dict().items())


def _handshake_headers(session: Session) -> dict[str, str]:
    return {
        "Cookie": _cookie_header(session),
        "Host": "wss-goofish.dingtalk.com",
        "Connection": "Upgrade",
        "Pragma": "no-cache",
        "Cache-Control": "no-cache",
        "User-Agent": UA_WEB,
        "Origin": "https://www.goofish.com",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }


@asynccontextmanager
async def connect(session: Session) -> AsyncIterator[ClientConnection]:
    """建立 WebSocket 连接（未 reg）。"""
    async with websockets.connect(
        WS_URL,
        additional_headers=_handshake_headers(session),
        ping_interval=None,
        max_size=4 * 1024 * 1024,
    ) as ws:
        yield ws


async def register(ws: ClientConnection, session: Session, token: str) -> None:
    """/reg + /r/SyncStatus/ackDiff。"""
    reg = {
        "lwp": "/reg",
        "headers": {
            "cache-header": "app-key token ua wv",
            "app-key": IM_APP_KEY,
            "token": token,
            "ua": UA_IM,
            "dt": "j",
            "wv": "im:3,au:3,sy:6",
            "sync": "0,0;0;0;",
            "did": session.device_id,
            "mid": generate_mid(),
        },
    }
    await ws.send(json.dumps(reg))
    current_ms = int(time.time() * 1000)
    ack_diff = {
        "lwp": "/r/SyncStatus/ackDiff",
        "headers": {"mid": generate_mid()},
        "body": [
            {
                "pipeline": "sync",
                "tooLong2Tag": "PNM,1",
                "channel": "sync",
                "topic": "sync",
                "highPts": 0,
                "pts": current_ms * 1000,
                "seq": 0,
                "timestamp": current_ms,
            }
        ],
    }
    await ws.send(json.dumps(ack_diff))


async def heartbeat_loop(ws: ClientConnection, interval: float = 15.0) -> None:
    """LWP /! 空心跳。"""
    while True:
        try:
            await ws.send(json.dumps({"lwp": "/!", "headers": {"mid": generate_mid()}}))
        except Exception as exc:  # noqa: BLE001
            logger.debug("heartbeat send failed: %s", exc)
            return
        await asyncio.sleep(interval)


def build_ack(msg: dict[str, Any]) -> dict[str, Any]:
    """对下行包回 code=200 ack。"""
    headers = msg.get("headers") or {}
    ack: dict[str, Any] = {
        "code": 200,
        "headers": {
            "mid": headers.get("mid") or generate_mid(),
            "sid": headers.get("sid", ""),
        },
    }
    for key in ("app-key", "ua", "dt"):
        if key in headers:
            ack["headers"][key] = headers[key]
    return ack


async def send_text(
    ws: ClientConnection, *, myid: str, cid: str, toid: str, text: str
) -> str:
    """发文本消息，返回 mid。"""
    return await _send_custom(
        ws,
        myid=myid,
        cid=cid,
        toid=toid,
        ctype=1,
        payload={"contentType": 1, "text": {"text": text}},
    )


async def send_image(
    ws: ClientConnection,
    *,
    myid: str,
    cid: str,
    toid: str,
    url: str,
    width: int,
    height: int,
) -> str:
    """发图片消息，返回 mid。"""
    return await _send_custom(
        ws,
        myid=myid,
        cid=cid,
        toid=toid,
        ctype=2,
        payload={
            "contentType": 2,
            "image": {
                "pics": [{"type": 0, "url": url, "width": width, "height": height}]
            },
        },
    )


async def _send_custom(
    ws: ClientConnection,
    *,
    myid: str,
    cid: str,
    toid: str,
    ctype: int,
    payload: dict[str, Any],
) -> str:
    mid = generate_mid()
    data_b64 = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
    msg = {
        "lwp": "/r/MessageSend/sendByReceiverScope",
        "headers": {"mid": mid},
        "body": [
            {
                "uuid": generate_uuid(),
                "cid": f"{cid}@goofish",
                "conversationType": 1,
                "content": {
                    "contentType": 101,
                    "custom": {"type": ctype, "data": data_b64},
                },
                "redPointPolicy": 0,
                "extension": {"extJson": "{}"},
                "ctx": {"appVersion": "1.0", "platform": "web"},
                "mtags": {},
                "msgReadStatusSetting": 1,
            },
            {"actualReceivers": [f"{toid}@goofish", f"{myid}@goofish"]},
        ],
    }
    await ws.send(json.dumps(msg))
    return mid


async def create_chat(ws: ClientConnection, *, myid: str, toid: str, item_id: str) -> str:
    """创建/复用单聊会话。"""
    mid = generate_mid()
    msg = {
        "lwp": "/r/SingleChatConversation/create",
        "headers": {"mid": mid},
        "body": [
            {
                "pairFirst": f"{toid}@goofish",
                "pairSecond": f"{myid}@goofish",
                "bizType": "1",
                "extension": {"itemId": item_id},
                "ctx": {"appVersion": "1.0", "platform": "web"},
            }
        ],
    }
    await ws.send(json.dumps(msg))
    return mid


async def collect_session_cids(
    session: Session, duration: float = 5.0
) -> list[dict[str, Any]]:
    """短时连 WS，收集 push 到的 session cid。"""
    token = get_access_token(session)
    acc: dict[str, dict[str, Any]] = {}

    async with connect(session) as ws:
        reg = {
            "lwp": "/reg",
            "headers": {
                "cache-header": "app-key token ua wv",
                "app-key": IM_APP_KEY,
                "token": token,
                "ua": UA_IM,
                "dt": "j",
                "wv": "im:3,au:3,sy:6",
                "sync": "0,0;0;0;",
                "did": session.device_id,
                "mid": generate_mid(),
            },
        }
        await ws.send(json.dumps(reg))
        ack_diff = {
            "lwp": "/r/SyncStatus/ackDiff",
            "headers": {"mid": generate_mid()},
            "body": [
                {
                    "pipeline": "sync",
                    "tooLong2Tag": "PNM,1",
                    "channel": "sync",
                    "topic": "sync",
                    "highPts": 0,
                    "pts": 0,
                    "seq": 0,
                    "timestamp": int(time.time() * 1000),
                }
            ],
        }
        await ws.send(json.dumps(ack_diff))

        hb = asyncio.create_task(heartbeat_loop(ws))
        deadline = time.time() + duration
        try:
            while time.time() < deadline:
                try:
                    raw = await asyncio.wait_for(
                        ws.recv(), timeout=max(0.1, deadline - time.time())
                    )
                except TimeoutError:
                    break
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                with suppress(Exception):
                    await ws.send(json.dumps(build_ack(msg)))

                for decoded in extract_push_messages(msg):
                    if not isinstance(decoded, dict):
                        continue
                    cid = str(decoded.get("sessionId") or "")
                    op = decoded.get("operation") or {}
                    sess_info = op.get("sessionInfo") if isinstance(op, dict) else None
                    if cid and isinstance(sess_info, dict):
                        ext = sess_info.get("extensions") or {}
                        entry = acc.setdefault(cid, {"cid": cid})
                        entry["session_type"] = (
                            sess_info.get("sessionType")
                            or decoded.get("chatType")
                            or entry.get("session_type", 0)
                        )
                        entry["item_id"] = str(ext.get("itemId") or entry.get("item_id", ""))
                        continue

                    meta = extract_meta_event(decoded)
                    if meta and meta.get("event") == "new_msg":
                        cid2 = meta["cid"]
                        entry = acc.setdefault(cid2, {"cid": cid2})
                        entry["last_msg_id"] = meta.get("msg_id", "")
                        entry["last_msg_ts"] = meta.get("ts", "")
        finally:
            hb.cancel()

    out: list[dict[str, Any]] = []
    for cid, entry in acc.items():
        out.append(
            {
                "cid": cid,
                "session_type": int(entry.get("session_type") or 0),
                "item_id": entry.get("item_id", "") or "",
                "last_msg_id": entry.get("last_msg_id", ""),
                "last_msg_ts": entry.get("last_msg_ts", ""),
            }
        )
    return out


async def collect_events(session: Session, duration: float = 15.0) -> list[dict[str, Any]]:
    """短时连 WS，收集推送消息与元事件。"""
    token = get_access_token(session)
    events: list[dict[str, Any]] = []
    async with connect(session) as ws:
        await register(ws, session, token)
        hb = asyncio.create_task(heartbeat_loop(ws))
        deadline = time.time() + duration
        try:
            while time.time() < deadline:
                try:
                    raw = await asyncio.wait_for(
                        ws.recv(), timeout=max(0.1, deadline - time.time())
                    )
                except TimeoutError:
                    break
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if msg.get("lwp") == "/s/para":
                    continue
                with suppress(Exception):
                    await ws.send(json.dumps(build_ack(msg)))
                for decoded in extract_push_messages(msg):
                    meta = extract_meta_event(decoded)
                    if meta is not None:
                        events.append(meta)
                        continue
                    item = extract_incoming_text(decoded)
                    if item and (item.get("send_message") or item.get("content_type") == 1):
                        events.append(item)
        finally:
            hb.cancel()
    return events


async def list_user_messages(
    session: Session, cid: str, limit_per_page: int = 20
) -> list[dict[str, Any]]:
    """一次性拉取指定会话历史消息。"""
    token = get_access_token(session)
    messages: list[dict[str, Any]] = []
    send_mid = generate_mid()
    req = {
        "lwp": "/r/MessageManager/listUserMessages",
        "headers": {"mid": send_mid},
        "body": [f"{cid}@goofish", False, 9007199254740991, limit_per_page, False],
    }

    async with connect(session) as ws:
        await register(ws, session, token)
        hb = asyncio.create_task(heartbeat_loop(ws))
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                with suppress(Exception):
                    await ws.send(json.dumps(build_ack(msg)))

                if msg.get("lwp") == "/s/vulcan":
                    await ws.send(json.dumps(req))
                    continue

                recv_mid = (msg.get("headers") or {}).get("mid", "")
                if recv_mid != send_mid:
                    continue

                body = msg.get("body") or {}
                models = body.get("userMessageModels") or []
                for um in models:
                    try:
                        ext = um["message"]["extension"]
                        data_b64 = um["message"]["content"]["custom"]["data"]
                        payload = json.loads(base64.b64decode(data_b64).decode("utf-8"))
                        messages.insert(
                            0,
                            {
                                "send_user_id": ext.get("senderUserId", ""),
                                "send_user_name": ext.get("reminderTitle", ""),
                                "message": payload,
                            },
                        )
                    except Exception as exc:  # noqa: BLE001
                        logger.debug("parse history item failed: %s", exc)

                has_more = body.get("hasMore") == 1
                if has_more:
                    send_mid = generate_mid()
                    req["headers"]["mid"] = send_mid
                    req["body"][2] = body.get("nextCursor")
                    await ws.send(json.dumps(req))
                else:
                    break
        finally:
            hb.cancel()
    return messages


def _decode_one(raw: str) -> dict[str, Any] | None:
    """明文 JSON → base64(JSON) → decrypt。"""
    if not isinstance(raw, str):
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(base64.b64decode(raw))
    except Exception:  # noqa: BLE001
        pass
    try:
        return json.loads(decrypt(raw))
    except Exception as exc:  # noqa: BLE001
        logger.debug("decrypt push failed: %s", exc)
        return None


def extract_push_messages(msg: dict[str, Any]) -> list[dict[str, Any]]:
    """解析 /s/vulcan 推送包（一帧可含多条）。"""
    try:
        data_list = msg["body"]["syncPushPackage"]["data"]
    except (KeyError, TypeError):
        return []
    if not isinstance(data_list, list):
        return []
    out: list[dict[str, Any]] = []
    for item in data_list:
        if not isinstance(item, dict):
            continue
        decoded = _decode_one(item.get("data", ""))
        if decoded is not None:
            out.append(decoded)
    return out


def extract_push_message(msg: dict[str, Any]) -> dict[str, Any] | None:
    """只取第一条推送。"""
    batch = extract_push_messages(msg)
    return batch[0] if batch else None


def extract_incoming_text(decoded: dict[str, Any]) -> dict[str, Any] | None:
    """从解码后的推送包提取消息事件。"""
    op = decoded.get("operation") if isinstance(decoded, dict) else None
    if isinstance(op, dict):
        content = op.get("content") or {}
        content_type = content.get("contentType")
        sess = op.get("sessionInfo") or {}
        sender = op.get("senderInfo") or {}
        reminder = content.get("reminder") or {}
        cid = str(decoded.get("sessionId") or sess.get("sessionId") or "")
        text = ""
        if content_type == 1:
            text = (content.get("text") or {}).get("text", "") or reminder.get(
                "reminderContent", ""
            )
        elif content_type == 101:
            custom = content.get("custom") or {}
            data_b64 = custom.get("data", "")
            if data_b64:
                try:
                    payload = json.loads(base64.b64decode(data_b64))
                    text = (payload.get("text") or {}).get("text", "")
                except Exception:  # noqa: BLE001
                    text = ""
            text = text or reminder.get("reminderContent", "")
        else:
            text = reminder.get("reminderContent", "")

        return {
            "event": "message",
            "cid": cid,
            "content_type": content_type,
            "send_user_id": str(
                sender.get("senderUserId", "") or reminder.get("senderUserId", "")
            ),
            "send_user_name": reminder.get("reminderTitle", ""),
            "send_message": text,
        }

    one = decoded.get("1") if isinstance(decoded, dict) else None
    if isinstance(one, dict):
        node = one.get("10")
        if isinstance(node, dict):
            cid_full = one.get("2", "")
            cid = cid_full.split("@")[0] if isinstance(cid_full, str) else ""
            return {
                "event": "message",
                "cid": cid,
                "send_user_id": node.get("senderUserId", ""),
                "send_user_name": node.get("reminderTitle", ""),
                "send_message": node.get("reminderContent", ""),
            }

    return None


def extract_meta_event(decoded: dict[str, Any]) -> dict[str, Any] | None:
    """识别 new_msg / read 元事件。"""
    if not isinstance(decoded, dict):
        return None
    one, two, three = decoded.get("1"), decoded.get("2"), decoded.get("3")

    if isinstance(one, list) and two == 2 and isinstance(three, str) and three.endswith(
        "@goofish"
    ):
        return {
            "event": "read",
            "cid": three.split("@")[0],
            "msg_ids": [str(x) for x in one],
            "status": decoded.get("4"),
            "ts": str(decoded.get("5", "")),
        }

    if isinstance(one, str) and one.endswith("@goofish") and two == 1 and isinstance(
        three, str
    ):
        return {
            "event": "new_msg",
            "cid": one.split("@")[0],
            "msg_id": three,
            "ts": str(decoded.get("4", "")),
        }

    return None


MessageHandler = Callable[[dict[str, Any], ClientConnection], Awaitable[None]]


async def run_forever(
    session: Session,
    handler: MessageHandler | None = None,
    *,
    refresh_every: float = 600.0,
) -> None:
    """常驻 IM 长连接（产品侧保活用；MCP 一般不调）。"""

    async def _keepalive() -> None:
        while True:
            await asyncio.sleep(refresh_every)
            try:
                refresh_login(session)
                logger.debug("login refreshed")
            except Exception as exc:  # noqa: BLE001
                logger.warning("login refresh failed: %s", exc)

    async def _one_session() -> None:
        token = get_access_token(session)
        async with connect(session) as ws:
            await register(ws, session, token)
            hb = asyncio.create_task(heartbeat_loop(ws))
            try:
                async for raw in ws:
                    try:
                        msg = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    with suppress(Exception):
                        await ws.send(json.dumps(build_ack(msg)))
                    if handler is not None:
                        try:
                            await handler(msg, ws)
                        except Exception as exc:  # noqa: BLE001
                            logger.exception("handler error: %s", exc)
            finally:
                hb.cancel()

    ka = asyncio.create_task(_keepalive())
    backoff = 1.0
    try:
        while True:
            try:
                logger.info("WS 连接中…")
                await _one_session()
                logger.info("WS 正常退出，3s 后重连")
                backoff = 1.0
                await asyncio.sleep(3)
            except websockets.exceptions.ConnectionClosed as exc:
                logger.warning("WS 断连：%s；%.1fs 后重连", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.exception("WS 会话异常：%s；%.1fs 后重连", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
    finally:
        ka.cancel()
