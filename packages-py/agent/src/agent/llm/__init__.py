"""LLM 接入层：LangChain ChatOpenAI + 供应商目录。

公开面只有下面这几个名字；``import agent`` **不会**把它们带进来，
要用就 ``from agent.llm import LlmClient``。
"""

from __future__ import annotations

from agent.llm.client import LlmClient, create_chat_model
from agent.llm.models import ChatResult, LlmSettings, Usage
from agent.llm.providers import CatalogProvider, get_provider, list_providers, resolve_settings

__all__ = [
    "CatalogProvider",
    "ChatResult",
    "LlmClient",
    "LlmSettings",
    "Usage",
    "create_chat_model",
    "get_provider",
    "list_providers",
    "resolve_settings",
]
