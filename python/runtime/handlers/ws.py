"""WSS IPC — Rust 启停长连接、发送消息、轮询入站事件。"""

from __future__ import annotations

import logging
from typing import Any

from runtime.wss.manager import get_wss_manager

logger = logging.getLogger("dingda.runtime.wss.handler")


async def handle_ws_connect(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    body = payload or {}
    account_id = str(body.get("account_id") or "").strip()
    cookies = body.get("cookies")
    auto_reply = bool(body.get("auto_reply", False))
    ai_settings = body.get("ai_settings")
    if not isinstance(cookies, list):
        return {"ok": False, "message": "cookies 必须为数组", "trace_id": trace_id}
    if ai_settings is not None and not isinstance(ai_settings, dict):
        return {"ok": False, "message": "ai_settings 必须为对象", "trace_id": trace_id}
    manager = get_wss_manager()
    result = await manager.connect(
        account_id,
        cookies,
        auto_reply=auto_reply,
        ai_settings=ai_settings,
    )
    result["trace_id"] = trace_id
    return result


async def handle_ws_disconnect(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    body = payload or {}
    account_id = str(body.get("account_id") or "").strip()
    if not account_id:
        return {"ok": False, "message": "account_id 必填", "trace_id": trace_id}
    result = await get_wss_manager().disconnect(account_id)
    result["trace_id"] = trace_id
    return result


async def handle_ws_send(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    body = payload or {}
    account_id = str(body.get("account_id") or "").strip()
    cid = str(body.get("cid") or "").strip()
    peer_id = str(body.get("peer_id") or "").strip()
    text = str(body.get("text") or "").strip()
    if not all([account_id, cid, peer_id, text]):
        return {
            "ok": False,
            "message": "account_id / cid / peer_id / text 必填",
            "trace_id": trace_id,
        }
    result = await get_wss_manager().send_message(account_id, cid=cid, peer_id=peer_id, text=text)
    result["trace_id"] = trace_id
    return result


async def handle_ws_status(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    body = payload or {}
    account_id = body.get("account_id")
    aid = str(account_id).strip() if account_id else None
    result = await get_wss_manager().status(aid)
    result["trace_id"] = trace_id
    return result


async def handle_ws_events_poll(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    body = payload or {}
    account_id = str(body.get("account_id") or "").strip()
    limit = body.get("limit")
    limit_int = int(limit) if isinstance(limit, int) else 50
    if not account_id:
        return {"ok": False, "message": "account_id 必填", "trace_id": trace_id}
    result = await get_wss_manager().poll_events(account_id, limit=limit_int)
    result["trace_id"] = trace_id
    return result


async def handle_ws_history(payload: dict[str, Any] | None, *, trace_id: str) -> dict[str, Any]:
    body = payload or {}
    account_id = str(body.get("account_id") or "").strip()
    cid = str(body.get("cid") or "").strip()
    if not account_id or not cid:
        return {
            "ok": False,
            "message": "account_id / cid 必填",
            "trace_id": trace_id,
            "messages": [],
        }
    result = await get_wss_manager().fetch_history(account_id, cid)
    result["trace_id"] = trace_id
    return result
