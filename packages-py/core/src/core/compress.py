"""Agent 上下文压缩（Headroom）。

职责：
    在消息进 LLM、Skill 注入块、CLI 工具大 JSON 回传前调用 headroom.compress，降低 token。
    供产品 Agent、外部 CLI prompt / tools.cli 出口共用。

设计说明：
    - ``DINGDA_HEADROOM=0`` 关闭；未安装 headroom-ai 时透传并打 warning
    - 不启动独立 proxy，避免与 Server ``8787`` 冲突
    - 工具 payload 压完会把身份字段还原（见 ``_IDENTITY_KEYS``）：工具 stdout 同时是
      给前端解析的机器契约，被换成占位符就等于商品数据丢了

使用示例：
    messages = compress_messages(messages, model="gpt-4o")
    text = compress_text(skill_block)
    payload = compress_tool_payload(payload, tool_name="search")
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("dingda.agent.compress")

DEFAULT_MODEL = os.getenv("DINGDA_LLM_MODEL", "gpt-4o").strip() or "gpt-4o"
# 工具 JSON 超过该字节数才压
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


def compress_text(text: str, *, model: str | None = None) -> str:
    """压缩大段纯文本（Skill 注入块等）；失败或关闭时原样返回。"""
    body = (text or "").strip()
    if not body or not headroom_enabled():
        return text
    compressed = compress_messages([{"role": "system", "content": body}], model=model)
    for msg in compressed:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if isinstance(content, str) and content.strip():
            return content
    return text


# 身份字段：删了或换了，下游就没法把这条商品认出来 / 显示出来。
#
# 为什么需要这份名单：压缩会把长字符串换成 `<<ccr:...>>` 占位符（不可逆）。这对
# 「给 LLM 省 token」是好事，但工具 stdout 同时是**机器契约** —— 前端要靠它把商品
# 渲染进结果面板。实测（2026-09-15）：`search` 返回 3 条商品，`title` 全变成
# `<<ccr:8150d6b866ad,string,499B>>`，抓取成功却面板恒为 0 条。
# 所以只压正文类大字段（desc / comments / content_text / ocr_text），身份字段原样保留。
_IDENTITY_KEYS = frozenset(
    {
        "item_id",
        "id",
        "title",
        "price",
        "url",
        "product_url",
        "platform",
        "seller_nick",
        "location",
        "image_url",
        "xsec_token",
    }
)


def _restore_identity(original: Any, compressed: Any) -> Any:
    """把被压缩替换掉的身份字段，从原文按同名键还原回去。

    headroom 只替换**字符串的值**、不动结构，所以两边可以并行遍历。结构对不上
    （比如条目数被改动）就原样返回压缩结果 —— 退化成压缩前的行为，不会更糟。
    """
    if isinstance(original, dict) and isinstance(compressed, dict):
        for key, value in original.items():
            if key in _IDENTITY_KEYS:
                compressed[key] = value
            elif key in compressed:
                compressed[key] = _restore_identity(value, compressed[key])
        return compressed
    if isinstance(original, list) and isinstance(compressed, list) and len(original) == len(compressed):
        for index, item in enumerate(original):
            compressed[index] = _restore_identity(item, compressed[index])
        return compressed
    return compressed


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
            return _restore_identity(payload, parsed)
        return payload
    return payload
