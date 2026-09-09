"""Agent 上下文压缩（Headroom）。

职责：
    在消息进 LLM / MCP 大 JSON 回传前调用 headroom.compress，降低 token。
    供产品 Agent 循环与 dingda-mcp 出口共用。

设计说明：
    - ``DINGDA_HEADROOM=0`` 关闭；未安装 headroom-ai 时透传并打 warning
    - 不启动独立 proxy，避免与 Server ``8787`` 冲突

使用示例：
    messages = compress_messages(messages, model="gpt-4o")
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("dingda.agent.compress")

DEFAULT_MODEL = os.getenv("DINGDA_LLM_MODEL", "gpt-4o").strip() or "gpt-4o"
# MCP / tool JSON 超过该字节数才压
DEFAULT_BYTE_THRESHOLD = 4096


def headroom_enabled() -> bool:
    """是否启用 Headroom（默认开）。"""
    value = os.getenv("DINGDA_HEADROOM", "1").strip().lower()
    return value not in {"0", "false", "no", "off"}


def compress_messages(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
) -> list[dict[str, Any]]:
    """压缩 chat messages；失败或关闭时原样返回。"""
    if not messages or not headroom_enabled():
        return messages
    try:
        from headroom import compress
    except ImportError:
        logger.warning("headroom-ai 未安装，跳过压缩")
        return messages

    target = (model or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    try:
        result = compress(messages, model=target)
    except Exception:
        logger.exception("headroom compress failed，透传原文")
        return messages

    saved = int(getattr(result, "tokens_saved", 0) or 0)
    before = int(getattr(result, "tokens_before", 0) or 0)
    after = int(getattr(result, "tokens_after", 0) or 0)
    logger.info(
        "headroom compress saved=%s before=%s after=%s model=%s",
        saved,
        before,
        after,
        target,
    )
    out = getattr(result, "messages", None)
    return list(out) if isinstance(out, list) and out else messages


def compress_tool_payload(
    payload: dict[str, Any],
    *,
    tool_name: str,
    model: str | None = None,
    byte_threshold: int = DEFAULT_BYTE_THRESHOLD,
) -> dict[str, Any]:
    """把 Tool 返回 dict 当 tool message 压一轮，再解析回 dict。

    体积小于阈值则跳过。解析失败时返回原文。
    """
    import json

    if not headroom_enabled():
        return payload
    raw = json.dumps(payload, ensure_ascii=False, default=str)
    if len(raw.encode("utf-8")) < byte_threshold:
        return payload

    messages = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_dingda",
                    "type": "function",
                    "function": {"name": tool_name, "arguments": "{}"},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_dingda", "content": raw},
    ]
    compressed = compress_messages(messages, model=model)
    for msg in reversed(compressed):
        if not isinstance(msg, dict) or msg.get("role") != "tool":
            continue
        content = msg.get("content")
        if not isinstance(content, str) or not content.strip():
            continue
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("headroom tool payload 非 JSON，保留原文 tool=%s", tool_name)
            return payload
        if isinstance(parsed, dict):
            return parsed
        return payload
    return payload
