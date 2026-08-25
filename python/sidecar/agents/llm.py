"""OpenAI 兼容 LLM 客户端 — 兼容层，委托 llm.client。"""

from llm.client import LlmClient
from llm.factory import create_provider, normalize_provider_type

# 历史 API
create_client = LlmClient.from_openai_compat


def chat(client: LlmClient, model: str, system: str, user: str) -> str:
    del model
    return client.chat(system, user)


__all__ = ["LlmClient", "chat", "create_client", "create_provider", "normalize_provider_type"]
