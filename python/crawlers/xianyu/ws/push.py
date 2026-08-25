"""syncPushPackage 解析 — 对齐 Rust `message/push.rs`。"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PushedSession:
    cid: str = ""
    item_id: str = ""
    item_title: str = ""
    updated_at: str = ""


@dataclass
class PushedMessage:
    cid: str = ""
    peer_id: str = ""
    peer_name: str = ""
    item_id: str = ""
    content: str = ""
    created_at_ms: int = 0


@dataclass
class PushBatch:
    sessions: list[PushedSession] = field(default_factory=list)
    messages: list[PushedMessage] = field(default_factory=list)


def decode_push_payload(raw: str) -> dict[str, Any] | None:
    text = raw.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        decoded = base64.b64decode(text)
        return json.loads(decoded.decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None


def parse_sync_push_package(msg: dict[str, Any]) -> PushBatch:
    data_list = (msg.get("body") or {}).get("syncPushPackage", {}).get("data")
    if not isinstance(data_list, list):
        return PushBatch()
    batch = PushBatch()
    seen: set[str] = set()
    for item in data_list:
        if not isinstance(item, dict):
            continue
        raw = item.get("data")
        if not isinstance(raw, str):
            continue
        decoded = decode_push_payload(raw)
        if decoded is None:
            continue
        _ingest_decoded(decoded, batch, seen)
    return batch


def extract_incoming_text(decoded: dict[str, Any]) -> PushedMessage | None:
    op = decoded.get("operation")
    if not isinstance(op, dict):
        return None
    content = op.get("content") or {}
    content_type = content.get("contentType")
    if content_type == 8:
        return None

    sess = op.get("sessionInfo") or {}
    sender = op.get("senderInfo") or {}
    reminder = content.get("reminder") or {}

    cid_raw = decoded.get("sessionId") or sess.get("sessionId") or ""
    cid = _extract_cid(str(cid_raw))
    if not cid:
        return None

    text = ""
    if content_type == 1:
        text = ((content.get("text") or {}).get("text")) or reminder.get("reminderContent") or ""
    elif content_type == 101:
        data_b64 = (content.get("custom") or {}).get("data")
        if isinstance(data_b64, str):
            try:
                payload = json.loads(base64.b64decode(data_b64).decode("utf-8"))
                text = (payload.get("text") or {}).get("text") or ""
            except (ValueError, json.JSONDecodeError):
                text = ""
        if not text:
            text = reminder.get("reminderContent") or ""
    else:
        text = reminder.get("reminderContent") or ""

    if not str(text).strip():
        return None

    peer_id = _json_str(sender.get("senderUserId")) or _json_str(reminder.get("senderUserId"))
    if not peer_id:
        return None

    extensions = sess.get("extensions") or {}
    item_id = _json_str(extensions.get("itemId")) or ""
    created_at_ms = int(
        decoded.get("createTime") or content.get("createTime") or 0,
    )

    return PushedMessage(
        cid=cid,
        peer_id=peer_id,
        peer_name=_json_str(reminder.get("reminderTitle")) or "",
        item_id=item_id,
        content=str(text).strip(),
        created_at_ms=created_at_ms,
    )


def _ingest_decoded(decoded: dict[str, Any], batch: PushBatch, seen: set[str]) -> None:
    cid_raw = str(decoded.get("sessionId") or "")
    sess_info = (decoded.get("operation") or {}).get("sessionInfo")
    if cid_raw and sess_info is not None:
        cid = _extract_cid(cid_raw)
        if cid and cid not in seen:
            seen.add(cid)
            ext = sess_info.get("extensions") or {}
            batch.sessions.append(
                PushedSession(
                    cid=cid,
                    item_id=_json_str(ext.get("itemId")) or "",
                    item_title=_json_str(ext.get("itemTitle")) or "",
                ),
            )

    meta_cid = _extract_new_msg_cid(decoded)
    if meta_cid:
        ts = _json_str(decoded.get("4")) or ""
        if meta_cid not in seen:
            seen.add(meta_cid)
            batch.sessions.append(
                PushedSession(cid=meta_cid, updated_at=ts),
            )
        elif ts:
            for session in batch.sessions:
                if session.cid == meta_cid and not session.updated_at:
                    session.updated_at = ts

    message = extract_incoming_text(decoded)
    if message is not None:
        batch.messages.append(message)


def _extract_new_msg_cid(decoded: dict[str, Any]) -> str | None:
    one = decoded.get("1")
    two = decoded.get("2")
    three = decoded.get("3")
    if (
        isinstance(one, str)
        and one.endswith("@goofish")
        and two == 1
        and isinstance(three, str)
        and three
    ):
        cid = _extract_cid(one)
        return cid or None
    return None


def _extract_cid(raw: str) -> str:
    return raw.split("@", 1)[0].strip()


def _json_str(value: Any) -> str | None:
    if isinstance(value, str) and value:
        return value
    if isinstance(value, (int, float)):
        return str(value)
    return None
