"""闲鱼 IM 业务封装：会话列表、历史与发送。

职责：
    对 Tool 暴露 chats / history / send 稳定函数；内部组合 mtop baseline 与 WebSocket，
    不启浏览器。

设计说明：
    - 平台：闲鱼（xianyu）；需 cookie 与 IM accessToken
    - 调用方：账号 / 渠道 HTTP，非 MCP Tool
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal

from src.channels.xianyu.guard import hold
from src.channels.xianyu.limiter import acquire
from src.channels.xianyu.mtop import call as mtop_call
from src.channels.xianyu.session import Session
from src.channels.xianyu.token import get_access_token
from src.channels.xianyu.ws import (
    collect_events,
    collect_session_cids,
    connect,
    create_chat,
    heartbeat_loop,
    list_user_messages,
    register,
    send_image,
    send_text,
)
from src.shared.errors import AppError

logger = logging.getLogger("dingda.channel.xianyu.message")


def _pick(data: dict[str, Any], *path: str, default: Any = "") -> Any:
    cur: Any = data
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def parse_session_row(item: dict[str, Any]) -> dict[str, Any]:
    """session.sync 单条 → 统一会话 record。"""
    session = item.get("session") or {}
    user_info = session.get("userInfo") or {}
    summary = _pick(item, "message", "summary", default={}) or {}
    return {
        "session_id": str(session.get("sessionId", "")),
        "peer_nick": user_info.get("nick", "") or user_info.get("fishNick", ""),
        "peer_user_id": str(user_info.get("userId", "")),
        "unread": summary.get("unread", 0),
        "last_msg": summary.get("summary", ""),
        "ts": summary.get("ts", 0),
        "session_type": session.get("sessionType", 0),
        "item_id": "",
        "source": "baseline",
    }


def watch_record(row: dict[str, Any]) -> dict[str, Any]:
    """WS 收集的 cid 骨架 → 统一会话 record。"""
    ts_raw = row.get("last_msg_ts") or 0
    try:
        ts = int(ts_raw)
    except (TypeError, ValueError):
        ts = 0
    return {
        "session_id": str(row["cid"]),
        "peer_nick": "",
        "peer_user_id": str(row.get("peer_user_id", "")),
        "unread": 0,
        "last_msg": "",
        "ts": ts,
        "session_type": int(row.get("session_type") or 0),
        "item_id": str(row.get("item_id", "")),
        "source": "watch",
    }


async def chats(
    cookie: str,
    *,
    fetch_num: int = 50,
    watch_secs: float = 0.0,
) -> dict[str, Any]:
    """拉会话列表：mtop baseline + 可选短时 WS 补 cid。"""
    session = Session.from_cookie_header(cookie)
    logger.info("chats start fetch_num=%s watch_secs=%s", fetch_num, watch_secs)
    raw = mtop_call(
        session,
        api="mtop.taobao.idlemessage.pc.session.sync",
        data={"fetchNum": int(fetch_num)},
        version="3.0",
        spm_cnt="a21ybx.im.0.0",
        auto_refresh=False,
    )
    data = raw.get("data") or {}
    baseline = [parse_session_row(s) for s in data.get("sessions") or []]
    known = {row["session_id"] for row in baseline}

    extras: list[dict[str, Any]] = []
    if watch_secs > 0:
        pushed = await collect_session_cids(session, duration=float(watch_secs))
        extras = [watch_record(w) for w in pushed if str(w["cid"]) not in known]

    logger.info("chats done baseline=%s watch=%s", len(baseline), len(extras))
    return {
        "sessions": baseline + extras,
        "has_more": bool(data.get("hasMore")),
        "total": len(baseline) + len(extras),
        "from_baseline": len(baseline),
        "from_watch": len(extras),
    }


async def history(
    cookie: str,
    cid: str,
    *,
    limit_per_page: int = 20,
) -> list[dict[str, Any]]:
    """拉指定 cid 历史消息。"""
    session = Session.from_cookie_header(cookie)
    logger.info("history start cid=%s", cid)
    messages = await list_user_messages(session, cid, limit_per_page=limit_per_page)
    logger.info("history done cid=%s count=%s", cid, len(messages))
    return messages


async def send(
    cookie: str,
    *,
    cid: str,
    toid: str,
    text: str = "",
    kind: Literal["text", "image"] = "text",
    image_url: str = "",
    image_width: int = 0,
    image_height: int = 0,
    item_id: str = "",
) -> dict[str, Any]:
    """向会话发一条消息。"""
    session = Session.from_cookie_header(cookie)
    logger.info("send start cid=%s kind=%s", cid, kind)
    with acquire("message.write"), hold():
        token = get_access_token(session)
        async with connect(session) as ws:
            await register(ws, session, token)
            hb = asyncio.create_task(heartbeat_loop(ws))
            try:
                if item_id:
                    await create_chat(ws, myid=session.unb, toid=toid, item_id=item_id)
                    await asyncio.sleep(0.5)

                if kind == "text":
                    if not text:
                        raise AppError("message.invalid", "kind=text 需要 text", status_code=400)
                    mid = await send_text(
                        ws, myid=session.unb, cid=cid, toid=toid, text=text
                    )
                elif kind == "image":
                    if not (image_url and image_width and image_height):
                        raise AppError(
                            "message.invalid",
                            "kind=image 需要 image_url / image_width / image_height",
                            status_code=400,
                        )
                    mid = await send_image(
                        ws,
                        myid=session.unb,
                        cid=cid,
                        toid=toid,
                        url=image_url,
                        width=image_width,
                        height=image_height,
                    )
                else:
                    raise AppError("message.invalid", f"不支持的 kind: {kind}", status_code=400)
                await asyncio.sleep(1.0)
            finally:
                hb.cancel()
    logger.info("send done cid=%s mid=%s", cid, mid)
    return {"cid": cid, "toid": toid, "kind": kind, "ok": True, "mid": mid}


async def watch(cookie: str, *, duration: float = 15.0) -> list[dict[str, Any]]:
    """短时收听 IM 下行事件（不对标 CLI 常驻 watch）。"""
    session = Session.from_cookie_header(cookie)
    logger.info("watch start duration=%s", duration)
    events = await collect_events(session, duration=float(duration))
    logger.info("watch done count=%s", len(events))
    return events

