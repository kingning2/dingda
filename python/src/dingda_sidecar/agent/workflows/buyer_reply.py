"""买家 IM 自动回复 — LangGraph 条件两节点。

供 WSS ``auto_reply`` 收到买家消息时调用。与比价六节点线性图不同：
本图用条件边决定是否花钱调 LLM。

流程::

    inbound ──► guard ──┬── skip=True ──► END
                        │                 （无 reply → 上层返回 None，不发消息；
                        │                  有 BARGAIN_LIMIT_REPLY → 发固定话术）
                        └── skip=False ─► generate ──► END
                                          （已有 reply 则透传；否则拼 prompt 调 LLM）

guard 依次检查（均不调模型）::

    AI 开关 → api_key → 营业时间 → 意图(NO_REPLY 跳过) → 议价轮数上限
"""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage

from dingda_sidecar.agent.graph.builder import bind_context
from dingda_sidecar.agent.graph.config import GraphConfig
from dingda_sidecar.agent.graph.context import GraphContext, StepCallback
from dingda_sidecar.agent.graph.model import BARGAIN_LIMIT_REPLY
from dingda_sidecar.agent.graph.state import BuyerReplyState
from dingda_sidecar.agent.prompts.buyer import system_prompt, user_prompt
from dingda_sidecar.agent.prompts.intent import Intent, route_intent
from dingda_sidecar.config.settings import AiSettings

BUYER_REPLY_STEPS: tuple[str, ...] = ("guard", "generate")


def _compile_buyer_reply_graph(ctx: GraphContext) -> Any:
    """编译：guard → 条件边 → generate | END。"""
    from langgraph.graph import END, StateGraph

    graph = StateGraph(BuyerReplyState)
    # 节点：各步职责（读/写字段见 BuyerReplyState）
    # 逐步进度暂不启用（比价图先用）；需要时给 bind_context 加 step=
    graph.add_node("guard", bind_context(ctx, guard_node))  # 零成本规则：开关/时段/意图/议价上限
    graph.add_node("generate", bind_context(ctx, generate_node))  # 固定话术透传，或拼 prompt 调 LLM

    graph.set_entry_point("guard")  # 先守卫，避免无谓调模型
    graph.add_conditional_edges(
        "guard",
        _route_after_guard,  # skip=True → end；否则 → generate
        {
            "generate": "generate",  # 过关：生成回复
            "end": END,  # 短路：不回复（或已带议价上限固定话术）
        },
    )
    graph.add_edge("generate", END)  # 生成完毕结束
    return graph.compile()


def _route_after_guard(state: BuyerReplyState) -> Literal["generate", "end"]:
    """条件路由：``skip`` → end，否则进入 generate。"""
    if state.get("skip"):
        return "end"
    return "generate"


def guard_node(state: BuyerReplyState, ctx: GraphContext) -> dict[str, Any]:
    """零成本守卫：规则判定，不调 LLM。

    返回 ``skip=True`` 短路；议价超限额外带 ``BARGAIN_LIMIT_REPLY``。
    """
    settings = ctx.config.ai_settings
    if settings is None or not settings.ai_enabled:
        return {"skip": True, "reply": ""}
    if not settings.api_key.strip():
        return {"skip": True, "reply": ""}
    if not settings.in_time_range():
        return {"skip": True, "reply": ""}

    intent = route_intent(state.get("user_message", ""))
    if intent == Intent.NO_REPLY:
        return {"skip": True, "reply": ""}

    bargain_count = int(state.get("bargain_count") or 0)
    if intent == Intent.PRICE and bargain_count >= settings.max_bargain_rounds:
        return {"skip": True, "reply": BARGAIN_LIMIT_REPLY, "intent": intent.value}

    return {"skip": False, "intent": intent.value}


def generate_node(state: BuyerReplyState, ctx: GraphContext) -> dict[str, str]:
    """生成回复：已有固定话术则透传，否则按意图拼 prompt 调 LLM。"""
    if state.get("reply"):
        return {"reply": str(state["reply"])}

    settings = ctx.config.ai_settings
    if settings is None:
        return {"reply": ""}

    intent = str(state.get("intent") or route_intent(state.get("user_message", "")).value)
    item_title = state.get("item_title") or ""
    item_id = state.get("item_id") or ""
    item_context = item_title or item_id or "（暂无商品信息）"

    system = system_prompt(intent, settings.custom_prompts)
    user = user_prompt(
        item_context=item_context,
        history=str(state.get("history") or ""),
        bargain_count=int(state.get("bargain_count") or 0),
        max_bargain_rounds=settings.max_bargain_rounds,
        max_discount_percent=settings.max_discount_percent,
        max_discount_amount=settings.max_discount_amount,
        user_message=state.get("user_message", ""),
    )

    response = ctx.model.invoke([SystemMessage(content=system), HumanMessage(content=user)])
    reply = str(getattr(response, "content", "") or "").strip()
    return {"reply": reply}


def run_buyer_reply(
    settings: AiSettings,
    inbound: dict[str, Any],
    *,
    on_step: StepCallback | None = None,
) -> str | None:
    """生成买家回复；``skip`` 且无话术时返回 None（上层不发送）。"""
    config = GraphConfig.from_ai_settings(settings)
    ctx = GraphContext(config, on_step=on_step, steps=BUYER_REPLY_STEPS)
    compiled = _compile_buyer_reply_graph(ctx)
    initial: BuyerReplyState = {
        "user_message": str(inbound.get("content") or ""),
        "peer_name": str(inbound.get("peer_name") or ""),
        "item_id": str(inbound.get("item_id") or ""),
        "item_title": str(inbound.get("item_title") or ""),
        "history": str(inbound.get("history") or ""),
        "bargain_count": int(inbound.get("bargain_count") or 0),
        "intent": "",
        "reply": "",
        "skip": False,
    }
    result = compiled.invoke(initial)
    if result.get("skip") and not result.get("reply"):
        return None
    reply = str(result.get("reply") or "").strip()
    return reply or None
