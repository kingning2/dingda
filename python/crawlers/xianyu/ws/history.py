"""历史消息解析 — 对齐 Rust ``message/history.rs``。

解码历史接口返回内容，提取可读文本供 IPC ``ws/history`` 与测试使用。"""

from __future__ import annotations

import base64
import json
from typing import Any


def parse_history_message(model: dict[str, Any]) -> dict[str, Any] | None:
    message = model.get("message")
    if not isinstance(message, dict):
        return None
    extension = message.get("extension") if isinstance(message.get("extension"), dict) else {}
    sender_user_id = str(extension.get("senderUserId") or "")
    sender_user_name = str(extension.get("reminderTitle") or "")
    content_node = message.get("content") if isinstance(message.get("content"), dict) else {}
    custom = content_node.get("custom") if isinstance(content_node.get("custom"), dict) else {}
    data = custom.get("data")
    if not isinstance(data, str):
        return None
    content = decode_history_content(data) or ""
    created_at_ms = 0
    for key in ("createAt", "createTime", "ts", "createTimeMs"):
        value = message.get(key)
        if isinstance(value, int | float):
            created_at_ms = int(value)
            break
    return {
        "sender_user_id": sender_user_id,
        "sender_user_name": sender_user_name,
        "content": content,
        "created_at_ms": created_at_ms,
    }


def decode_history_content(data_base64: str) -> str | None:
    try:
        text = base64.b64decode(data_base64).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    trimmed = text.strip()
    try:
        value = json.loads(trimmed)
    except json.JSONDecodeError:
        return trimmed
    extracted = _extract_text(value)
    return extracted if extracted is not None else trimmed


def _extract_text(node: Any) -> str | None:
    if isinstance(node, str):
        return node
    if not isinstance(node, dict):
        return None
    text = node.get("text")
    if isinstance(text, str):
        return text
    if isinstance(text, dict) and isinstance(text.get("text"), str):
        return str(text["text"])
    if isinstance(node.get("content"), str):
        return str(node["content"])
    if isinstance(node.get("title"), str):
        return str(node["title"])
    return None
