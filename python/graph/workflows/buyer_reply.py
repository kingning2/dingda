"""买家 IM 自动回复 — LangGraph 编排（guard → generate）。

两节点条件图，供 WSS ``auto_reply`` 在收到买家消息时调用：

- ``guard``   — 零成本守卫，依次检查：AI 开关 / api_key / 营业时间段 /
  意图路由（寒暄等 NO_REPLY 直接跳过）/ 议价轮数超限。
  不该回复时置 ``skip=True`` 短路，其中议价超限会带固定话术 ``BARGAIN_LIMIT_REPLY``。
- ``generate``— 拼 system + user prompt 后 LLM 生成回复；若 guard 已给出
  固定话术则直接透传，不再调模型。

``_route_after_guard`` 条件边：skip → END（无话术时上层返回 None 表示不回复），
否则 → generate。"""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.messages import HumanMessage, SystemMessage

from agents.intent import Intent, route_intent
from agents.prompt import system_prompt, user_prompt
from config.settings import AiSettings
from graph.core.config import GraphConfig
from graph.core.context import GraphContext
from graph.core.graph import bind_context
from graph.core.model import BARGAIN_LIMIT_REPLY
from graph.core.state import BuyerReplyState


def _compile_buyer_reply_graph(ctx: GraphContext) -> Any:
    """编译买家回复图：guard 条件分支到 generate 或 END。

    与比价流不同，这里是条件图——guard 的判定决定是否花钱调 LLM。
    """
    from langgraph.graph import END, StateGraph

    graph = StateGraph(BuyerReplyState)
    graph.add_node("guard", bind_context(ctx, guard_node))
    graph.add_node("generate", bind_context(ctx, generate_node))
    graph.set_entry_point("guard")
    graph.add_conditional_edges(
        "guard",
        _route_after_guard,
        {"generate": "generate", "end": END},
    )
    graph.add_edge("generate", END)
    return graph.compile()


def _route_after_guard(state: BuyerReplyState) -> Literal["generate", "end"]:
    """guard 后的条件路由：skip 短路结束，否则进入生成。"""
    if state.get("skip"):
        return "end"
    return "generate"


def guard_node(state: BuyerReplyState, ctx: GraphContext) -> dict[str, Any]:
    """零成本守卫：不调 LLM，只做规则判定。

    任一条件不满足即置 ``skip=True``；唯一例外是议价超限——仍跳过生成，
    但带上固定婉拒话术让上层直接发送。
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
    """生成回复：guard 已写入固定话术时透传，否则按意图拼 prompt 调 LLM。"""
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


def run_buyer_reply(settings: AiSettings, inbound: dict[str, Any]) -> str | None:
    """生成买家回复；无需回复时返回 None（skip 且无固定话术）。"""
    config = GraphConfig.from_ai_settings(settings)
    ctx = GraphContext(config)
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
