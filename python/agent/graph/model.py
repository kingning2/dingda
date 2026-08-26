"""LangChain ChatModel 工厂 — Graph 节点统一用生态内置模型。

依赖 ``langchain-openai.ChatOpenAI``（OpenAI 兼容端点覆盖 DeepSeek / Qwen /
Claude 代理 / Gemini 兼容网关等）。``normalize_provider_type`` 仅用于配置归一。
"""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from config.settings import AiSettings

BARGAIN_LIMIT_REPLY = "抱歉，这个价格已经是最优惠的了，不能再便宜了哦！"


def create_chat_model(settings: AiSettings) -> BaseChatModel:
    """构造内置 ChatOpenAI；不再走自研 HTTP Provider。"""
    # ponytail: 仅装了 langchain-openai；anthropic/gemini 亦走兼容端点
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.model_name,
        api_key=settings.api_key or None,
        base_url=settings.base_url or None,
        temperature=0.5,
        max_tokens=8192,
    )
