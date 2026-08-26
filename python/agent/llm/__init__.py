"""LLM 能力包（位于 graph）— 类型归一 + Embedding；Chat 用 LangChain 内置。

节点请经 ``agent.graph.model.create_chat_model`` / ``GraphContext.llm`` 调用。
"""

from agent.llm.embeddings import embed, normalize_base_url
from agent.llm.factory import normalize_provider_type
from agent.llm.models import EmbeddingRequest, EmbeddingResponse, LlmError

__all__ = [
    "EmbeddingRequest",
    "EmbeddingResponse",
    "LlmError",
    "embed",
    "normalize_base_url",
    "normalize_provider_type",
]
