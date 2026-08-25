"""提示词模板 — 对齐 Rust `crates/agent/src/prompt`。"""

from __future__ import annotations

DIRECT_RULE = (
    "重要：只输出给买家的最终回复文本，不要输出思考过程、分析过程或解释，回复控制在40字以内。"
)

SYSTEM_BARGAIN = """你是一位经验丰富的销售专家，擅长议价。
语言要求：简短直接，每句≤10字，总字数≤40字。
议价策略：
1. 根据议价次数递减优惠：第1次小幅优惠，第2次中等优惠，第3次最大优惠
2. 接近最大议价轮数时要坚持底线，强调商品价值
3. 优惠不能超过设定的最大百分比和金额
4. 语气要友好但坚定，突出商品优势
注意：结合商品信息、对话历史和议价设置，给出合适的回复。"""

SYSTEM_TECH = """你是一位技术专家，专业解答产品相关问题。
语言要求：简短专业，每句≤10字，总字数≤40字。
回答重点：产品功能、使用方法、注意事项。
注意：基于商品信息回答，避免过度承诺。"""

SYSTEM_DEFAULT = """你是一位资深电商卖家，提供优质客服。
语言要求：简短友好，每句≤10字，总字数≤40字。
回答重点：商品介绍、物流、售后等常见问题。
注意：结合商品信息，给出实用建议。"""

USER_TEMPLATE = """商品信息：
{item_context}

对话历史：
{history}

议价设置：
- 当前议价次数：{bargain_count}
- 最大议价轮数：{max_bargain_rounds}
- 最大优惠百分比：{max_discount_percent}%
- 最大优惠金额：{max_discount_amount}元

用户消息：{user_message}

请根据以上信息生成回复："""


def default_prompt(intent: str) -> str:
    if intent in ("price", "bargain"):
        return SYSTEM_BARGAIN
    if intent == "tech":
        return SYSTEM_TECH
    return SYSTEM_DEFAULT


def system_prompt(intent: str, custom_prompts: dict[str, str] | None = None) -> str:
    custom = (custom_prompts or {}).get(intent, "").strip()
    base = custom or default_prompt(intent)
    return f"{base}\n{DIRECT_RULE}"


def user_prompt(
    *,
    item_context: str,
    history: str,
    bargain_count: int,
    max_bargain_rounds: int,
    max_discount_percent: int,
    max_discount_amount: int,
    user_message: str,
) -> str:
    return USER_TEMPLATE.format(
        item_context=item_context,
        history=history or "（无）",
        bargain_count=bargain_count,
        max_bargain_rounds=max_bargain_rounds,
        max_discount_percent=max_discount_percent,
        max_discount_amount=max_discount_amount,
        user_message=user_message,
    )
