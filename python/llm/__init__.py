"""LLM 能力包 — 统一客户端、Provider 工厂与 Embedding。

再导出常用类型与工厂，供 Graph / sidecar agent 兼容层使用。"""

from llm.client import LlmClient
from llm.factory import create_provider, normalize_provider_type
from llm.models import ChatMessage, ChatRequest, ChatResponse, LlmError

__all__ = [
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "LlmClient",
    "LlmError",
    "create_provider",
    "normalize_provider_type",
]
