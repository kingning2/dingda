"""本地意图检测 — 对齐 Rust ``crates/agent/src/intent.rs``。

按关键词将买家消息路由到议价 / 技术 / 默认 / 不回复等意图，供 buyer_reply guard 使用。"""

from __future__ import annotations

from enum import StrEnum


class Intent(StrEnum):
    NO_REPLY = "no_reply"
    PRICE = "price"
    TECH = "tech"
    DEFAULT = "default"


NO_REPLY_KEYWORDS = ("谢谢", "好的", "嗯嗯", "再见", "没了", "不需要了", "收到", "好的谢谢", "ok")
TECH_KEYWORDS = (
    "怎么用",
    "参数",
    "坏了",
    "故障",
    "设置",
    "说明书",
    "功能",
    "用法",
    "教程",
    "驱动",
    "规格",
    "型号",
    "接口",
)
PRICE_KEYWORDS = (
    "便宜",
    "优惠",
    "刀",
    "降价",
    "价格",
    "多少钱",
    "能少",
    "还能",
    "最低",
    "底价",
    "实诚价",
    "包个邮",
    "砍价",
    "少点",
)


def route_intent(text: str) -> Intent:
    clean = "".join(ch for ch in text if ch.isalnum() or ch == "元" or ch.isdigit())
    if any(keyword in clean for keyword in NO_REPLY_KEYWORDS):
        return Intent.NO_REPLY
    if any(keyword in clean for keyword in TECH_KEYWORDS):
        return Intent.TECH
    has_price_pattern = ("元" in clean and any(ch.isdigit() for ch in clean)) or (
        clean.startswith("能少") and any(ch.isdigit() for ch in clean[2:])
    )
    if has_price_pattern:
        return Intent.PRICE
    if any(keyword in clean for keyword in PRICE_KEYWORDS):
        return Intent.PRICE
    return Intent.DEFAULT
