"""LangChain ChatModel 工厂 — Graph 节点统一走 LangGraph 生态 LLM。"""

from __future__ import annotations

from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import RunnableLambda

from config.settings import AiSettings

BARGAIN_LIMIT_REPLY = "抱歉，这个价格已经是最优惠的了，不能再便宜了哦！"


def create_chat_model(settings: AiSettings) -> BaseChatModel:
    """按 Provider 构造 LangChain ChatModel；exotic provider 回落到现有 LlmClient。"""
    kind = settings.normalized_provider_type()
    if kind in {"openai_compatible", "anthropic", "gemini"}:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.model_name,
            api_key=settings.api_key or None,
            base_url=settings.base_url or None,
            temperature=0.5,
            max_tokens=8192,
        )
    return _legacy_llm_runnable(settings)


def _legacy_llm_runnable(settings: AiSettings) -> BaseChatModel:
    """dashscope_app 等 LangChain 未直连的 provider，经 LlmClient 适配为 Runnable。"""
    from llm.client import LlmClient

    client = LlmClient(settings.to_provider_settings())

    def invoke(messages: list[BaseMessage], *_args: Any, **_kwargs: Any) -> AIMessage:
        system_parts: list[str] = []
        user_parts: list[str] = []
        for message in messages:
            role = getattr(message, "type", "")
            content = str(getattr(message, "content", ""))
            if role == "system":
                system_parts.append(content)
            else:
                user_parts.append(content)
        reply = client.chat("\n".join(system_parts), "\n".join(user_parts))
        return AIMessage(content=reply)

    return RunnableLambda(invoke)  # type: ignore[return-value]
