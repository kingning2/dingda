"""闲鱼 mtop 爬虫 IPC — 商品列表/详情、用户资料、会话头信息。

从 payload 取 Cookie，调用 crawlers.xianyu.item/profile 并包装为 IPC 响应。"""

from __future__ import annotations

import logging
from typing import Any

from crawlers.xianyu.item import fetch_item_detail, fetch_seller_items
from crawlers.xianyu.profile import fetch_message_headinfo, fetch_user_profile
from crawlers.xianyu.ws.cookies import cookies_to_header, credential_to_cookie_header

logger = logging.getLogger("dingda.runtime.xianyu_mtop")


def _cookie_from_payload(payload: dict[str, Any]) -> str:
    cookies = payload.get("cookies")
    if isinstance(cookies, list):
        return cookies_to_header(cookies)
    cookie = payload.get("cookie") or payload.get("cookie_str") or ""
    return credential_to_cookie_header(str(cookie))


def handle_xianyu_seller_items(
    payload: dict[str, Any] | None,
    *,
    trace_id: str,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"ok": False, "message": "payload 缺失", "trace_id": trace_id}
    cookie = _cookie_from_payload(payload)
    user_id = str(payload.get("user_id") or "").strip()
    max_pages = int(payload.get("max_pages") or 0)
    if not cookie or not user_id:
        return {"ok": False, "message": "cookie / user_id 必填", "trace_id": trace_id}
    try:
        items, updated_cookie = fetch_seller_items(cookie, user_id, max_pages=max_pages)
    except Exception as error:  # noqa: BLE001
        logger.warning("seller_items 失败: %s", error, extra={"trace_id": trace_id})
        return {"ok": False, "message": str(error), "trace_id": trace_id}
    return {
        "ok": True,
        "items": items,
        "cookie": updated_cookie,
        "trace_id": trace_id,
    }


def handle_xianyu_item_detail(
    payload: dict[str, Any] | None,
    *,
    trace_id: str,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"ok": False, "message": "payload 缺失", "trace_id": trace_id}
    cookie = _cookie_from_payload(payload)
    item_id = str(payload.get("item_id") or "").strip()
    if not cookie or not item_id:
        return {"ok": False, "message": "cookie / item_id 必填", "trace_id": trace_id}
    try:
        detail, updated_cookie = fetch_item_detail(cookie, item_id)
    except Exception as error:  # noqa: BLE001
        logger.warning("item_detail 失败: %s", error, extra={"trace_id": trace_id})
        return {"ok": False, "message": str(error), "trace_id": trace_id}
    return {
        "ok": True,
        "detail": detail,
        "cookie": updated_cookie,
        "trace_id": trace_id,
    }


def handle_xianyu_user_profile(
    payload: dict[str, Any] | None,
    *,
    trace_id: str,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"ok": False, "message": "payload 缺失", "trace_id": trace_id}
    cookie = _cookie_from_payload(payload)
    if not cookie:
        return {"ok": False, "message": "cookie 必填", "trace_id": trace_id}
    try:
        profile, updated_cookie = fetch_user_profile(cookie)
    except Exception as error:  # noqa: BLE001
        logger.warning("user_profile 失败: %s", error, extra={"trace_id": trace_id})
        return {"ok": False, "message": str(error), "trace_id": trace_id}
    return {
        "ok": True,
        "profile": profile,
        "cookie": updated_cookie,
        "trace_id": trace_id,
    }


def handle_xianyu_message_headinfo(
    payload: dict[str, Any] | None,
    *,
    trace_id: str,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"ok": False, "message": "payload 缺失", "trace_id": trace_id}
    cookie = _cookie_from_payload(payload)
    session_id = str(payload.get("session_id") or "").strip()
    item_id = str(payload.get("item_id") or "").strip()
    if not cookie or not session_id:
        return {"ok": False, "message": "cookie / session_id 必填", "trace_id": trace_id}
    try:
        data = fetch_message_headinfo(cookie, session_id, item_id)
    except Exception as error:  # noqa: BLE001
        logger.warning("message_headinfo 失败: %s", error, extra={"trace_id": trace_id})
        return {"ok": False, "message": str(error), "trace_id": trace_id}
    return {"ok": True, "data": data, "trace_id": trace_id}
